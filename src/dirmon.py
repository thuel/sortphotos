""" Work heavly based on https://thomassileo.name/blog/2013/12/12/tracking-changes-in-directories-with-python/
"""

from __future__ import print_function, unicode_literals
import os
import json
import hashlib
import argparse
import subprocess as sp

def filehash(filepath, blocksize=4096):
    """ Return the hash hexdigest for the file `filepath', processing the file
    by chunk of `blocksize'.

    :type filepath: str
    :param filepath: Path to file

    :type blocksize: int
    :param blocksize: Size of the chunk when processing the file

    """
    sha = hashlib.sha256()
    with open(filepath, 'rb') as fp:
        while 1:
            data = fp.read(blocksize)
            if data:
                sha.update(data)
            else:
                break
    return sha.hexdigest()

def init_state(p):
    """ Initialize the state of the filenames and paths

    p: path to root directory for which an inventory should be
      created.
    """
    files = []
    subdirs = []
    for root, dirs, filenames in os.walk(p):
        for subdir in dirs:
            subdirs.append(os.path.relpath(os.path.join(root, subdir), p))

        for f in filenames:
            files.append(os.path.relpath(os.path.join(root, f), p))

    index = {}
    for f in files:
        outp = sp.check_output(['exiftool', '-j', '-xmp:Subject', '-xmp:HierarchicalSubject', os.path.join(p, f)])
        tag_dict = json.loads(outp)
        #print(tag_dict)
        filepath = os.path.join(p, f)
        index[f] = (os.path.getatime(filepath), os.path.getmtime(filepath), tag_dict[0].get('Subject', None), tag_dict[0].get('HierarchicalSubject', None))

    index2 = {}
    for f in files:
        index2[os.path.basename(f)] = index[f]

    return dict(files=files, subdirs=subdirs, index=index, index2=index2)

def save_state(d, filename):
    """ Save the json representation of a dict object to filename.

    d: dictionary to save
    filename: file name of the file in which to save d
    """
    with open(filename, 'w') as f:
        f.write(json.dumps(d))

def load_state(filename):
    """ returns a state dictionary from a file.

    filename: file name to load the json representation of a dictionary
      object from.
    """
    with open(filename, 'r') as f:
        return json.loads(f.read())

def compute_diff(dir_base, dir_cmp):
    data = {}
    data['deleted'] = list(set(dir_cmp['files']) - set(dir_base['files']))
    data['created'] = list(set(dir_base['files']) - set(dir_cmp['files']))
    data['updated'] = []
    data['deleted_dirs'] = list(set(dir_cmp['subdirs']) - set(dir_base['subdirs']))

    for f in set(dir_cmp['files']).intersection(set(dir_base['files'])):
        if dir_base['index'][f] != dir_cmp['index'][f]:
            data['updated'].append(f)

    return data

def update_path_check_file(state, rootdir, filename):
    """ Update the control file in which files with changing paths are recorded.

    state: dictionary with last known state
    rootdir: the path to the directory within which the files should be monitored
    filename: name of the file in which updates are recorded
    """
    check_dict = load_state(filename)
    update_dict = check_dict['pathchecker']  # Load an extisting check file
    # Make sure the file contains information about moved files (not changed tags)
    latest_state = init_state(rootdir)  # Compute the actual state of the directory monitored
    # Compute the difference between the last saved state and the actual state.
    diff = compute_diff(latest_state, state)
    # Check for files moved
    files = update_dict.get('files', {})  # Load already changed files from check file
    for deleted_file in diff['deleted']:
        if os.path.basename(deleted_file) in (os.path.basename(newf) for newf in diff['created']):
            new_file = ""
            for newf in diff['created']:
                if os.path.basename(newf) == os.path.basename(deleted_file):
                    new_file = newf
            files[deleted_file] = new_file  # update a moved file with its new information
    update_dict['files'] = files # on the backup side: check if dirname exists else mkdir first.

    subdirs = update_dict.get('subdirs', [])
    subdirs.extend(diff['deleted_dirs'])
    update_dict['subdirs'] = list(set(subdirs)) # on the backup side: check if there are no regular files in the dir before removing it.

    save_state(check_dict, filename)

def update_tag_check_file(state, rootdir, filename):
    """ Update the control file in which files with changing tags are recorded.

    state: dictionary with last known state
    rootdir: the path to the directory within which the files should be monitored
    filename:  name of the file in which updates are recorded.
    """
    check_dict = load_state(filename)
    update_dict = check_dict['tagchecker'] # load tagchecker dict from existing check file
    latest_state = init_state(rootdir)
    diff = compute_diff(latest_state, state)
    # Check for files with changed tags
    files = update_dict.get('files', {})
    for updated_file in diff['updated']:
        # Check if tags got updated
        adate, mdate, subjects, hierarchical_subjects = latest_state['index'][updated_file]  # get date time modified
        subject_changed = (subjects != state['index'][updated_file][2])
        hier_subject_changed = (hierarchical_subjects != state['index'][updated_file][3])
        if subject_changed or hier_subject_changed:
            files[updated_file] = (subjects, hierarchical_subjects, adate, mdate)
    update_dict['files'] = files

    save_state(check_dict, filename)

def main(state_file, check_file, rootdir):
    if not os.path.exists(check_file):
        state = init_state(rootdir)
        save_state(state, state_file)
        save_state({'pathchecker': {}, 'tagchecker': {}}, check_file)
    else:
        state = load_state(state_file)
        update_path_check_file(state, rootdir, check_file)
        update_tag_check_file(state, rootdir, check_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--statefile", "-s", type=str,
                        default=r"state_file.json",
                        help="file name of state file.")
    parser.add_argument("--checkfile", "-c", type=str,
                        default=r"check_file.json",
                        help="file name of the check file.")
    parser.add_argument("--root", "-r", type=str,
                        default=r".", help="path to the directory to be monitored.")
    args = parser.parse_args()
    main(args.statefile, args.checkfile, args.root)
