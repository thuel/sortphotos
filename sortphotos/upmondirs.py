from __future__ import print_function, unicode_literals
import os
import json
import hashlib
import argparse
import logging
import logging.handlers as handlers
import subprocess as sp
from threading import Thread
from queue import Queue
from pathlib import Path

logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=logformat)

logger=logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = handlers.RotatingFileHandler(Path(__file__).name + '.log', maxBytes=1000, backupCount=2)
handler.setLevel(logging.INFO)

formatter = logging.Formatter(logformat)
handler.setFormatter(formatter)

logger.addHandler(handler)

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

    d: dictionary as loaded by load_changes.
    root: path to root of monitored directory tree on backup.
    """
    logger.debug("Parameters for move_files: d: {}, root: {}".format(d, root))
    if root is None:
        root=r"."
    for key in d:
        src = os.path.normpath(root + "/" + key)
        dst = os.path.normpath(root + "/" + d[key])
        dst_dir = os.path.dirname(dst)
        try:
            if not os.path.exists(dst_dir):
                logger.debug("Trying to make dir: {}".format(dst_dir))
                os.makedirs(dst_dir)
            logger.debug("Moving {} to {}".format(src, dst))
            os.rename(src, dst)
        except:
            logger.warning("Couldn't move {} to {}. File either\
                          doesn't exist or is already moved.".format(src, dst))

def rm_subdirs(sd, r):
    """ Remove empty subdirs.

    sd: list of subdirectories.
    r: path to target directory (monitor root).
    """
    for subdir in sd:
        try:
            dirpath = os.path.normpath(r + "/" + subdir)
            if not os.listdir(dirpath):
                logger.debug("Removing directory: {}".format(dirpath))
                os.removedirs(dirpath)
        except FileNotFoundError:
            logger.warning("Couldn't find Directory {} to delete.".format(dirpath))
        except Exception as e:
            logger.error("Exception occoured: {}".format(e))

def update_tags(d, root=r'.'):
    """ Update the xmp tags of the files in the dict given.

    d: dictionary with files and their new tags. As well as atime and mtime
    root: path to the root of directory tree to update.
    """
    logger.debug("Paramters for update_tags: d: {}, root: {}".format(d, root))
    if root is None:
        root = r'.'
    for key in d:
        dst = os.path.normpath(root + "/" + key)
        subjs, hiersubjs, adate, mdate = d[key]
        cmd = "exiftool -overwrite_original -sep ',' '-xmp:Subject={}' '-xmp:HierarchicalSubject={}' {}".format(",".join(subjs), ",".join(hiersubjs), dst.replace(" ", "\ "))
        logger.debug("Command to be run: {}".format(cmd))
        try:
            out = sp.check_output([cmd], shell=True)
            logger.info("Output while updating tags for file {}: {}".format(dst, out))
            os.utime(dst, (adate, mdate))
        except Exception as e:
            logger.error("Exception: {}".format(e))
            logger.warning("Couldn't update tags of file {}.".format(dst))

def thread_worker(q, root='.'):
    if root is None:
        root = '.'
    while True:
        input = q.get()
        if input == None:
            break
        key, value = input
        try:
            update_tags({key: value}, root)
        except:
            logger.error("Couldn't update tags for input: {}".format(input))
        finally:
            q.task_done()

def main():
    # parse command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("checkfile", type=str, help="Path to check file.")
    parser.add_argument("root", type=str, help="Path to root of checked directory.")
    args = parser.parse_args()

    check_file = args.checkfile
    rootdir = args.root

    d = load_changes(check_file)
    # first check for files moved
    if d['pathchecker'].get('files', None) or d['pathchecker'].get('subdirs', None):
        files = d['pathchecker']['files']
        if files != {}:
            move_files(files, rootdir)
        subdirs = d['pathchecker']['subdirs']
        logger.debug("subdirs in main: {}".format(subdirs))
        if subdirs:
            rm_subdirs(subdirs, rootdir)
    else:
        logger.info("No directories renamed. Therefore nothing to do.")
    if d['tagchecker'].get('files', None):
        files = d['tagchecker']['files']
        if files != {}:
            threads = []
            jobs = Queue()

            for _ in range(32):
                thread = Thread(target=thread_worker, args=(jobs, rootdir))
                thread.setDaemon(True)
                thread.start()
                threads.append(thread)
            logger.debug("Setup threads. Adding jobs to queue...")

            for key, values in files.items():
                jobs.put((key, values))

            logger.debug("Waiting for jobs to finish")
            jobs.join()

            for thread in threads:
                jobs.put(None)

            for thread in threads:
                thread.join()
            logger.debug("Finished joining threads.")

            #update_tags(files, rootdir)
            """
            Could be uncommented and move in an if statement if working
            without threads should be accomplished.
            Actually threading is setup to indirectly call update_tags()
            via the thread_worker.
            """
    else:
        logger.info("No tags changed. Therefore nothing to do.")

if __name__ == "__main__":
    main()
