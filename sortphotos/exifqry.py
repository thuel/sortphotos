""" Modul with tools to query exif data from foto files.
"""

import os
import subprocess as sp
import re
import json
import sys
import argparse
import logging
import threading
import dill as pickle
from multiprocessing import Process, Pool

from sortphotos import ExifTool
import face_recognition
from face_recognition import face_locations
from face_recognition import load_image_file
from face_recognition import compare_faces

logging.basicConfig(level=logging.DEBUG)

def get_exif_xmp_hierarchicalsubject(src, recursive=True):
    """ Return a list of exif xmp:hierarchicalsubject for all files in dst.

    dst: path to base folder in which every image is querried.
    """
    if recursive is None:
        recursive = True
    args = ['-j', '-a', '-xmp:hierarchicalsubject']
    if recursive:
        args.append('-r')
    args.append(src)
    with ExifTool(verbose='verbose') as e:
        sys.stdout.flush()
        meta = e.get_metadata(*args)
    logging.debug("Metadata gathered from {}: {}".format(src, meta))
    return meta

def get_exif_xmp_subject(src, recursive=True):
    """ Return a list of exif xmp:subject for all files in dst.

    dst: path to base folder in which every image is querried.
    """
    if recursive is None:
        recursive = True
    args = ['-j', '-a', '-xmp:subject']
    if recursive:
        args.append('-r')
    args.append(src)
    with ExifTool(verbose='verbose') as e:
        sys.stdout.flush()
        meta = e.get_metadata(*args)
    logging.debug("Metadata gathered from {}: {}".format(src, meta))
    return meta

def get_exif_xmp_subjects(src, recursive=True):
    """ Return a list of exif xmp:subject and xmp:hierarchicalsubject for all files in dst.

    dst: path to base folder in which every image is querried.
    """
    if recursive is None:
        recursive = True
    args = ['-j', '-a', '-xmp:subject', '-xmp:hierarchicalsubject']
    if recursive:
        args.append('-r')
    args.append(src)
    with ExifTool(verbose='verbose') as e:
        sys.stdout.flush()
        meta = e.get_metadata(*args)
    logging.debug("Metadata gathered from {}: {}".format(src, meta))
    return meta

def get_num_facelocations(filename):
    """ Return a filename and number of persons tuple.
    """
    try:
        img = load_image_file(filename)
        array = face_locations(img)
        logging.debug("The array: {}".format(array))
        return (filename, len(array))
    except:
        return None

def get_fotos_num_persons(src, num=1, recursive=True):
    """ Return a list of filepath with fotos with only one person.

    src: source directory to be querried.
    num: number of persons to be on the foto. -1 = all
    recursive: inicates wether the query is recursive.
    """
    procs = []
    num_list = []
    for root, dirs, filenames in os.walk(src):
        """ Version with Process():
        for f in filenames:
            path = os.path.join(root, f)
            try:
                proc = Process(target=get_num_facelocations, args=(path,))
                procs.append(proc)
                proc.start()
            except Exception as e:
                logging.error("Exception: {}".format(e))

        for proc in procs:
            proc.join()
        """
        # Version with Pool():
        for f in filenames:
            procs.append(os.path.join(root, f))
    pool = Pool(processes=150)
    data = pool.map(get_num_facelocations, [f for f in procs])
    pool.close()
    result = []
    for filename, faces in data:
        if num == -1:
            result.append(filename)
        if faces == num:
            result.append(filename)
    return result


def num_pattern_in_tags(src, tag, num=1, recursive=True):
    """ Returns a list with the filepaths of the fotos with num occurences of tag.

    src: path to files
    tag: pattern or tag to search in exif meta data (hierarchicalsubject), regex allowed
    num: number of matches to control for. -1 = all.
    recursive: search the source recursively.
    """
    if recursive is None:
        recursive = True
    if num is None:
        num = 1
    meta = get_exif_xmp_hierarchicalsubject(src, recursive)
    regex = re.compile(tag)
    result = []
    for f in meta:
        d = f.get('HierarchicalSubject', None)
        logging.debug('d in num_pattern_in_tags: {}'.format(d))
        if d and 'leute' in d:
            res = {f['SourceFile']: []}
            for item in d:
                r = regex.findall(item)
                if len(r) > 0:
                    logging.debug('Found Match!!! {}'.format(r))
                    res[f['SourceFile']] += r
                    logging.debug('The variable res is: {} with value length: {}'.format(res, len(res[f['SourceFile']])))
                    if num == -1:
                        result.append(res)
            logging.debug('{}: with length: {} and num: {}'.format(len(res[f['SourceFile']]) == num, len(res[f['SourceFile']]), num))
            if len(res[f['SourceFile']]) == num:
                result.append(res)
    return result

def flatten_tags(tag_dicts):
    result = {}
    for tag_dict in tag_dicts:
        if tag_dict:
            for filename, tags in list(tag_dict.items()):
                flat_tags = []
                for tag in tags:
                    print(tag)
                    flat_tags.append(tag.split('|')[-1])
                result[filename] = flat_tags
    return result

def scan_known_people_in_dict(known_people_dict):
    """ Return tuple of two list with names and face encodings.

    known_people_dict: dict as returned from num_pattern_in_tags(src, 'leute\|.*\|.*', num=1)
      and processed by flatten_tags().
    """

    def face_encoder(index, result, filename):
        img = face_recognition.load_image_file(filename)
        encodings = face_recognition.face_encodings(img)

        if len(encodings) > 1:
            logging.warning("WARNING: More than one face found in {}. Only considering the first face.".format(filename))

        if len(encodings) == 0:
            logging.warning("WARNING: No faces found in {}. Ignoring file.".format(filename))
        else:
            result[index] = encodings[0]

    int_known_names = {}
    int_known_face_encodings = {}
    threads = []

    for index, tpl in enumerate(list(known_people_dict.items())):
        scan_thread = threading.Thread(target=face_encoder, args=(index, int_known_face_encodings, tpl[0]))
        scan_thread.start()
        threads.append(scan_thread)

        int_known_names[index] = tpl[1][0]

    for thread in threads:
        thread.join()

    known_names = []
    known_face_encodings = []

    for key in int_known_face_encodings:
        known_names.append(int_known_names[key])
        known_face_encodings.append(int_known_face_encodings[key])

    return known_names, known_face_encodings

def save_names_encodings_lists(names, encodings, filename):
    with open(filename, 'wb') as f:
        result = [names, encodings]
        f.write(pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))

def load_names_encodings_lists(filename):
    with open(filename, 'rb') as f:
        names, encodings = pickle.loads(f.read())
    return names, encodings

def save_best_matches(src, dst, recursive=True):
    """ Save names and face encodings for best matches to file.

    src: folder to search for images and persons.
    dst: file to save names and encodings lists.
    recursive: indicate if src should be searched recursive.
    """
    names, encodings = scan_known_people_in_dict(flatten_tags(num_pattern_in_tags(src, '^leute\|.*\|.*$', num=1)))
    unique_names = set(names)
    best_matches = []
    for name in unique_names:
        matches = [encoding for n, encoding in zip(names, encodings) if n == name]
        e_counts = []
        for m in matches:
            r = compare_faces(matches, m, 0.4)
            count = 0
            for similar in r:
                if similar:
                    count += 1
            e_counts.append(count)

        print(name, e_counts)
        name_max = max(e_counts)
        index = e_counts.index(name_max)
        best_matches.append((name, matches[index]))
    return best_matches

def main():
    """ Main function to run the tools.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=str, default='.',\
                        help='The folder to be querried for exif information')
    parser.add_argument('--tag', '-t', type=str,\
                       help='Specify a tag to be querried by exiftool')
    parser.add_argument('--flat', action='store_true',\
                        help='Only search the source directory for fotos')
    parser.add_argument('--numfaces', type=int, \
                        help='Get a list of one person fotos from source directory')

    args = parser.parse_args()

    recursive = True
    if args.flat:
        recursive = False

    tag = ''
    if args.tag:
        tag = args.tag.lower()
    if tag == 'xmp:hierarchicalsubject':
        get_exif_xmp_hierarchicalsubject(args.source, recursive)
    if tag == 'xmp:subject':
        get_exif_xmp_subject(args.source, recursive)
    if tag == 'subjects':
        get_exif_xmp_subjects(args.source, recursive)

    if args.numfaces:
        get_fotos_num_persons(args.source, args.numfaces, recursive)

if __name__ == "__main__":
    main()

