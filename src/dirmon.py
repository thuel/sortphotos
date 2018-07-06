""" Work heavly based on https://thomassileo.name/blog/2013/12/12/tracking-changes-in-directories-with-python/
"""

from __future__ import print_function, unicode_literals
import os
import json
import hashlib
import argparse

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
        index[f] = os.path.getmtime(os.path.join(p, f))
        
    return dict(files=files, subdirs=subdirs, index=index)

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

def update_check_file(state, rootdir, filename):
    """ Update the control file in which files with changing paths are recorded.

    state: dictionary with last known state
    rootdir: the path to the directory within which the files should be monitored
    filename: name of the file in which updates are recorded
    """
    update_dict = load_state(filename)
    latest_state = init_state(rootdir)
    diff = compute_diff(latest_state, state)
    files = update_dict.get('files', {})
    for deleted_file in diff['deleted']:
        if os.path.basename(deleted_file) in (os.path.basename(newf) for newf in diff['created']):
            new_file = ""
            for newf in diff['created']:
                if os.path.basename(newf) == os.path.basename(deleted_file):
                    new_file = newf
            files[deleted_file] = new_file
    update_dict['files'] = files # on the backup side: check if dirname exists else mkdir first.

    subdirs = update_dict.get('subdirs', [])
    subdirs.extend(diff['deleted_dirs'])
    update_dict['subdirs'] = subdirs # on the backup side: check if there are no regular files in the dir before removing it.
    
    if update_dict != load_state(filename):
        save_state(update_dict, filename)
    

def main(state_file, check_file, rootdir):
    if not os.path.exists(check_file):
        state = init_state(rootdir)
        save_state(state, state_file)
        save_state({}, check_file)
    else:
        state = load_state(state_file)
        update_check_file(state, rootdir, check_file)

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
