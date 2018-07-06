from __future__ import print_function, unicode_literals
import os
import json
import hashlib
import argparse
import logging

logging.basicConfig(level=logging.DEBUG)

def load_changes(filename):
    """ Return a dict with files for which the path changed.

    filename: path to file which contains a json representation
      of a python containing file names as keys and a dict with
      old and new path as values.
    """
    with open(filename, 'r') as f:
        return json.loads(f.read())

def move_files(d, root=r"."):
    """ Move the files according to the check directory.

    d: directory as loaded by load_changes.
    r: path to root of monitored directory tree on backup.
    """
    logging.debug("Parameters for move_files: d: {}, root: {}".format(d, root))
    if root is None:
        root=r"."
    for key in d:
        src = os.path.normpath(root + "/" + key)
        dst = os.path.normpath(root + "/" + d[key])
        dst_dir = os.path.dirname(dst)
        try:
            if not os.path.exists(dst_dir):
                logging.debug("Trying to make dir: {}".format(dst_dir))
                os.makedirs(dst_dir)
            logging.debug("Moving {} to {}".format(src, dst))
            os.rename(src, dst)
        except:
            logging.debug("Couldn't move {} to {}. File either\
                          doesn't exist or is already moved.".format(src, dst))

def rm_subdirs(sd, r):
    """ Remove empty subdirs.

    sd: list of subdirectories.
    r: path to target directory (monitor root).
    """
    for subdir in sd:
        dirpath = os.path.normpath(r + "/" + subdir)
        if not os.listdir(dirpath):
            logging.debug("Removing directory: {}".format(dirpath))
            os.removedirs(dirpath)

def main(check_file, rootdir):
    d = load_changes(check_file)
    if d != {}:
        files = d['files']
        if files != {}:
            move_files(files, rootdir)
        subdirs = d['subdirs']
        logging.debug("subdirs in main: {}".format(subdirs))
        if subdirs:
            rm_subdirs(subdirs, rootdir)
    else:
        logging.info("No directories renamed. Therefore nothing to do.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("checkfile", type=str, help="Path to check file.")
    parser.add_argument("root", type=str, help="Path to root of checked directory.")
    args = parser.parse_args()
    main(args.checkfile, args.root)
