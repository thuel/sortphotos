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
import itertools
import dill as pickle
import numpy as np
import multiprocessing
from multiprocessing import Process, Pool

from sortphotos import ExifTool
from sortphotos import upmondirs
import face_recognition
from face_recognition import face_locations
from face_recognition import load_image_file
from face_recognition import face_distance
from face_recognition import face_recognition_cli

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
    """ Return a list of tag_dicts where parent tags are removed.

    tag_dicts: list of tag dicts, where a tag dict has the following form:
      {filename: [hierarchical tag 1, hierarchical tag 2, ...]}
    returns: list of tag_dicts with parent tags removed from hierarchical
      tags: {filename: [tag 1, tag 2, ...]}
    """

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

def list_of_people_tags(src):
    """ Return a dict of hierarchical tags where the key is equal to the flat tag.

    src:  either a list of hierarchical tags or the source to directory with fotos
      with exif xmp hierarchical tags.
    """
    result = []
    if isinstance(src, list):
        result = src
    else:
        data = num_pattern_in_tags(src, 'leute.*', num=-1)
        for d in data:
             for i in list(d.values()):
                 r = []
                 for entry in i:
                     r.append(entry)
                 result.extend(r)
    return {i.split('|')[-1]: i for i in list(set(result))}

def get_files_dict(paths_hiertags_dict):
    """ Convert a dictionary with paths and hierarchical tags to a files dictionary.

    paths_hiertags_dict: dict as returned by path_with_hierarchical_tags().
    Returns: a files dictionary which is a dictionary with file paths as keys and
      tuples of the following form as values: (list(xmp:subject), list(xmp:hierarchicalsubject),
      access time, modified time).
    """
    result = {}
    for (key1, value1), (key2, value2) in zip(paths_hiertags_dict.items(), flatten_tags([paths_hiertags_dict]).items()):
        result[key1] = (value2, value1, os.path.getatime(key1), os.path.getmtime(key1))
    return result

def scan_known_people_in_dict(known_people_dict):
    """ Return two lists. One with names and one with face encodings.

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

def best_matches(src, recursive=True):
    """ Return a list of names and a list of the best matching face encoding for those names.

    src: directory to search for images and persons or a list containing a list
      of names and a list with corresponding encodings.
    recursive: indicate if src should be searched recursive.
    return: list of names and list of the best matching encodings to these names.
    """
    if not isinstance(src, str):
        names, encodings = src
    else:
        names, encodings = scan_known_people_in_dict(flatten_tags(num_pattern_in_tags(src, '^leute\|.*\|.*$', 1, recursive)))
    unique_names = set(names)
    best_matches_names = []
    best_matches_encodings = []
    for name in unique_names:
        matches = [encoding for n, encoding in zip(names, encodings) if n == name]
        if len(matches) == 1:
            continue
        e_counts = []
        for m in matches:
            r = face_distance(matches, m)
            r2 = np.where((r>0.))
            r = r[r2]
            if r is not []:
                e_counts.append(r.sum())
            print(e_counts)

        if e_counts is not []:
            name_min = min(e_counts)
            print("Minimum from list: {}".format(min(e_counts)))
            index = e_counts.index(name_min)
            best_matches_names.append(name)
            best_matches_encodings.append(matches[index])

    return best_matches_names, best_matches_encodings

def tag_recognized_faces(known_faces, image_to_check, with_tags=True, recursive=True, tolerance=0.6, show_distance=False, cpus=-1, tags_to_apply={}):
    """ Add xmp hierarchical subject with name of known faces to fotos.

    Adapted version from face_recognition_cli by Adam Geitgey (https://adamgeitgey.com/)

    known_faces: directory with fotos with known persons or a list containing a list
      of names and a list with corresponding encodings.
    image_to_check: path to the directory with fotos to recognize and tag faces in.
    with_tags: indicates wheter the fotos in known_faces contain xmp tags with peoples
      names.
    recursive: indicate if image_to_check should be searched recursive.
    tags_to_apply: dict of names and their corresponding hierarchical tag. E.g. as returned
      by list_of_people_tags. If an empty dict ist given, then only the names are attached
      to the xmp subject (no hierarchical subject).
    """
    if with_tags is None:
        with_tags = True
    if recursive is None:
        recursive = True
    if cpus is None:
        cpus=-1
    if tags_to_apply is None:
        tags_to_apply = {}

    if not isinstance(known_faces, str):
        logging.debug("Working with names and encodings already in memory")
        known_names, known_face_encodings = known_faces
        logging.debug("tagging with these names: {}".format(known_names))
    elif with_tags:
        logging.debug("Getting names and encodings from files with xmp:hierarchicalsubject tags.")
        known_names, known_face_encodings = scan_known_people_in_dict(flatten_tags(num_pattern_in_tags(src, '^leute\|.*\|.*$', 1, recursive)))
    else:
        logging.debug("Getting names and encodings with face_recognition_cli.scan_known_people.")
        known_names, known_face_encodings = face_recognition_cli.scan_known_people(src)

    if recursive and os.path.isdir(image_to_check):
        dir_list = [image_to_check]
        for root, dirs, filenames in os.walk(image_to_check):
            for subdir in dirs:
                dir_list.append(os.path.join(root, subdir))

    # Multi-core processing only supported on Python 3.4 or greater
    if (sys.version_info < (3, 4)) and cpus != 1:
        logging.warning("WARNING: Multi-processing support requires Python 3.4 or greater. Falling back to single-threaded processing!")
        cpus = 1

    if os.path.isdir(image_to_check):
        data = []
        for dir in dir_list:
            if cpus == 1:
                data.extend([face_recognition_cli.test_image(image_file, known_names, known_face_encodings,
                                                 tolerance, show_distance) for image_file in face_recognition_cli.image_files_in_folder(dir)])
            else:
                logging.debug("Start multicore processing")
                data.extend(process_images_in_process_pool(face_recognition_cli.image_files_in_folder(dir),
                                                                    known_names, known_face_encodings, cpus, tolerance, show_distance))

        helper_list = []
        for e in data:
            if e is not None:
                for i in e:
                    print(i)
                    helper_list.append(i)
        data = helper_list
        logging.debug("data as from the double for loop: {}".format(data))
        for d in data:
            print('!!! {}'.format(d))
        data = [x for x in data if x is not None] # Eventually include unknown persons
        logging.debug("data before sorting it: {}".format(data))
        data = sorted(data, key=lambda x: x[0])
        logging.debug("data after being sorted: {}".format(data))
        tags = path_with_tags(data)
        logging.debug("tags: {}".format(tags))

        logging.debug("tags_to_apply is: {}".format(tags_to_apply))
        if tags_to_apply != {}:
            logging.debug("Start getting hierarchical tags...")
            hierarchical_tags = path_with_hierarchical_tags(tags, tags_to_apply)
            upmondirs.update_tags(get_files_dict(hierarchical_tags, '/'))
        else:
            return tags
    else:
        face_recognition_cli.test_image(image_to_check, known_names, known_face_encodings, tolerance, show_distance)

    # Writing to tag: args for ExifTool: -xmp:hierarchicalsubject+=TAG

def path_with_tags(data):
    """ Return dictionary with path as keys and a list of tags as values.

    Input to the function is a list of tuples with path, name, distance.
    """
    result = {}
    for tpl in data:
        logging.debug("tpl is: {}".format(tpl))
        lst = result.get(tpl[0], [])
        logging.debug("lst is: {}".format(lst)) # ev. unknown persons to be checked here.
        if lst == []:
            lst = [tpl[1]]
        else:
            lst.append(tpl[1])
        result[tpl[0]] = lst
        logging.debug("At end of for loop, result is: {}".format(result))
    return result

def path_with_hierarchical_tags(data, h_tags):
    """ Returns a dictionary with path as keys and a list of hierarchical tags as values.

    Input to the function is the return value of path_with_tags, e.g. a dictionary with
    paths as keys and a list of tags as values. Secondly the parent hierarchical tag has to
    be provided.

    data:  dictionary with pahts as keys and lists of tags/names as values
    h_tags: list of hierarchical tags to be used
    """
    # TODO: Get list of known hierarchical tags / to be stored together with known faces.
    logging.debug("h_tags: {}".format(h_tags))
    result = {}
    for key, value in list(data.items()):
        tags = result.setdefault(key, [])
        logging.debug("Checking hierarchical tags for these names: {}".format(value))
        for name in value:
            logging.debug("name to test: {}".format(name))
            if name in h_tags:
                tags.append(h_tags[name])
            else:
                tags.append(h_tags['unbekannt'])
        if result[key] is not None:
            result[key] = list(set(tags))
    logging.debug("result dict: {}".format(result))
    return result

def set_exif_hierarchical_tags(path, tags):
    """ Add the hierarchical tags to xmp data of the file provided.

    path:  path to file to which xmp hierarchical subjects should be added.
    tags:  list of hierarchical tags to be applied.
    """
    pass

def process_images_in_process_pool(images_to_check, known_names, known_face_encodings, number_of_cpus, tolerance, show_distance):
    """ Slitly adapted version from face_recognition_cli by Adam Geitgey (https://adamgeitgey.com/)
    """

    if number_of_cpus == -1:
        processes = None
    else:
        processes = number_of_cpus

    # macOS will crash due to a bug in libdispatch if you don't use 'forkserver'
    context = multiprocessing
    if "forkserver" in multiprocessing.get_all_start_methods():
        context = multiprocessing.get_context("forkserver")

    pool = context.Pool(processes=processes)
    logging.debug('got pool')

    function_parameters = zip(
        images_to_check,
        itertools.repeat(known_names),
        itertools.repeat(known_face_encodings),
        itertools.repeat(tolerance),
        itertools.repeat(show_distance),
        itertools.repeat(True) # param for get_output
    )

    data = pool.starmap(face_recognition_cli.test_image, function_parameters)
    pool.close()
    return data

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

