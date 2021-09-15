#!/usr/bin/env python3

import argparse
import csv
import logging
import os

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List

import yacf

__app__ = "tl"
__version__ = (0, 1, 0)


@dataclass
class Record:
    ts_start: datetime
    ts_end: datetime = None
    tags: str = "default"

    def duration(self) -> int:
        """Calculates the duration in seconds and returns it.

        :return: Duration in seconds
        :rtype: int
        """
        if self.ts_end is None:
            return 0

        return (self.ts_end - self.ts_start).total_seconds


class RecordSet:
    def __init__(self, recs: List[Record]):
        """Creates a new instance of a RecordSet. Is a primitive way to maintain
        newly added records.

        :param recs: List of initial records.
        :type recs: List[Record]
        """
        self._recs = recs
        self._marker = len(recs)

    @property
    def closed(self) -> bool:
        """Indicates weather the record set is closed.

        :return: Last record is closed
        :rtype: bool
        """
        return self._recs[-1].ts_end is not None

    def add(self, rec: Record):
        """Adds a new record to the record set. Can just add a new record to the
        set if it is closed, meaning, the last record has an ts_end.

        :param rec: To be added record
        :type rec: Record
        """
        assert self.closed
        self._recs.append(rec)

    def new_recs(self):
        return self._recs[self._marker:]


def version():
    v = ".".join(map(str, __version__))
    return f"  {__app__} - time logger v{v}"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tl - Time Logger Command Line Utility",
        description="""
Command line utility to record working time. The time will be stored in a folder
which can be synchronized with a git repository, to work as a primitive solution
of a backup. One can use the tool by simply calling the start and stop function.
Further, one can equip records with a set of tags, to allow certain evaluations.

WARNING: This tool is just a prototype of a rapid development process. The final
         version will be most likely rewritten in the programming language Rust.
        """,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=version(),
        help="Print version information and exit.",
    )

    parser.add_argument(
        "cmd",
        nargs=1,
        choices=["start", "stop"],
        help="Start or close a time recording",
    )

    parser.add_argument(
        "-t",
        "--tags",
        nargs="+",
        default="default",
    )
    
    return parser


def load_recs(path):
    pass

def main():

    argp = build_parser()
    args = argp.parse_args()

    lvl = logging.DEBUG

    # Initialize logging
    formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s] %(message)s')
    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    ch.setFormatter(formatter)
    log = logging.getLogger(__app__)
    log.setLevel(lvl)
    log.addHandler(ch)

    log.debug("Loading configuration...")
    cfg = yacf.Configuration('./config.toml').load()
    log.debug("Loaded configuration.")

    year, month, day = date.today().year, date.today().month, date.today().day
    fname = os.path.join(cfg.get('database.directory'), f"{year}-{month}-{day}.csv")

    log.debug(f"Touching {fname}...")
    os.makedirs(Path(fname).parent)
    Path(fname).touch(exist_ok=True)
    log.debug(f"Touched {fname}")

    log.debug("Loading file...")
    recs = load_recs(fname)
    log.debug("Loaded file.")




if __name__ == "__main__":
    main()
