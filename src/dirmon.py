from __future__ import print_function, unicode_literals
import os
import json
import hashlib
import argparse

def init_state(p):
    """ Initialize the state of the filenames and paths

    p: path to root directory for which an inventory should be
      created.
    """
    d = {}
    for root, subdirs, filenames in os.walk(p):
        for f in filenames:
            d[hashlib.sha256(f).hexdigest()] = root
    return d

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

def update_check_file(state, rootdir, filename):
    """ Update the control file in which files with changing paths are recorded.

    state: dictionary with last known state
    rootdir: the path to the directory within which the files should be monitored
    filename: name of the file in which updates are recorded
    """
    update_dict = load_state(filename)
    for root, subdirs, filenames in os.walk(rootdir):
        for f in filenames:
            filehex = hashlib.sha256(f).hexdigest()
            state_value = state.get(filehex, None)
            if state_value is not None:
                if state_value != root:
                    update_dict[f] = {'old' : state[filehex], 'new' : root}
    if update_dict != {}:
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
