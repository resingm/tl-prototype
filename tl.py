#!/usr/bin/env python3

import argparse
import csv
import logging
import os

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Set

import yacf
from pretty_tables import PrettyTables

__app__ = "tl"
__version__ = (0, 1, 0)


class IllegalOperation(Exception):
    def __init__(self, message):
        self.message = message


@dataclass
class Record:
    ts_start: datetime
    ts_stop: datetime = None
    tags: Set = None

    @property
    def duration(self) -> int:
        """Calculates the duration in seconds and returns it.

        :return: Duration in seconds
        :rtype: int
        """
        if self.ts_stop is None:
            return 0

        return (self.ts_stop - self.ts_start).total_seconds()

    @property
    def closed(self) -> bool:
        """Defines weather the last record is closed or not.

        :return: Is record closed?
        :rtype: bool
        """
        return not any([
            self.ts_stop is None,
            self.ts_start == self.ts_stop,
        ])

    @staticmethod
    def deserialize(*args) -> "Record":
        """Deserializes some data fields into a record.

        :return: Record parsed from the values.
        :rtype: Record
        """
        if len(args) != 3:
            vals = ", ".join(args)
            raise Exception(f"Cannot deserialize the values [{vals}] to a Record.")

        x, y, z = float(args[0]), float(args[1]), args[2].split(' ')
        return Record(
            datetime.fromtimestamp(x),
            datetime.fromtimestamp(y),
            set(z),
        )

    def serialize(self) -> tuple:
        """Serializes the data into an iterable that has the data format used
        to write it to a file.

        :raises Exception: [description]
        :raises ValueError: [description]
        :return: [description]
        :rtype: tuple
        """
        return (
            self.ts_start.timestamp(),
            self.ts_stop.timestamp(),
            " ".join(self.tags),
        )


class RecordSet:
    def __init__(self, recs: List[Record]):
        """Creates a new instance of a RecordSet. Is a primitive way to maintain
        newly added records.

        :param recs: List of initial records.
        :type recs: List[Record]
        """
        self._recs = recs
        self._marker = len(recs)

        self._tags = []
        [self._tags.extend(r.tags) for r in self._recs]
        self._tags = set(self._tags)

    def __str__(self) -> str:
        status = "closed" if self.closed else "open"
        return f"RecordSet[len={len(self._recs)}] <{status}>"

    @property
    def closed(self) -> bool:
        """Indicates weather the record set is closed.

        :return: Last record is closed
        :rtype: bool
        """
        return self.empty or self._recs[-1].closed

    @property
    def empty(self) -> bool:
        """Indicates whether the record set is empty.

        :return: true, if no records in the set, otherwise false
        :rtype: bool
        """
        return len(self._recs) == 0

    @property
    def size(self) -> int:
        return len(self._recs)

    def generate_stats(self) -> Dict:
        """Generates a dictionary and sums up the durations per tag.

        :return: Dict, with tags as keys and durations as values
        :rtype: Dict
        """
        summary = {}

        for t in self._tags:
            recs = list(filter(lambda x: t in x.tags, self._recs))
            recs = map(lambda x: x.duration, recs)
            summary[t] = sum(recs)

        return summary

    def get_all(self):
        return self._recs

    def get_new(self):
        return self._recs[self._marker:]

    def reset_rec(self):
        """Resets the currently open record and deletes it. The open record
        will be deleted from the set.
        """
        if self.closed:
            raise IllegalOperation("Can not reset record. Current record is closed.")

        self._recs.pop()

    def restart_rec(self):
        """Restarts the current record. This means, the currently open records
        start time will be updated to the current timestamp.
        """
        tags = self._recs[-1].tags
        self.reset_rec()
        self.start_rec(tags)

    def start_rec(self, tags: Set):
        """Adds a new open record to the recording. Can just add a new record
        to the set if it is closed, meaning
            recs[-1].ts_stop == recs[-1].ts_start

        :param tags: Tags of the new record
        :type tags: str
        """
        if not self.closed:
            raise IllegalOperation("Cannot open a new record. Current record is open.")

        ts = datetime.now()
        self._recs.append(Record(ts, ts, tags))
        self._tags |= tags

    def stop_rec(self):
        """Closes the currently open record.
        """
        if self.closed:
            raise IllegalOperation("Cannot close record. Current record is open.")

        self._recs[-1].ts_stop = datetime.now()


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
        choices=["start", "stats", "stop", "reset", "restart"],
        help="Start or close a time recording",
    )

    parser.add_argument(
        "-t",
        "--tags",
        nargs="+",
        default=[],
    )

    return parser

def format_stats(workdate: str, stats: Dict, timeformat: str = 'H') -> str:
    """Formats statistics for a given date.

    :param workdate: The date from when the statistics are evaluated.
    :type workdate: date
    :param stats: Dictionary of statistics per tag.
    :type stats: Dict
    :return: [description]
    :rtype: str
    """
    tags = list(stats.keys())
    tags.sort()
    vals = []

    for t in tags:
        v = timedelta(seconds=stats[t])
        v = v.seconds / (3600)
        vals.append(round(v, 2))

    rows = [list(x) for x in zip(tags, vals)]

    table = PrettyTables.generate_table(
        headers=['Tag', f'Time ({timeformat})'],
        rows=rows,
        empty_cell_placeholder='-',
    )

    title = f"{workdate.isoformat()}"
    underline = "=" * len(title)
    return f"{title}\n{underline}\n\n{table}"

    
def read_recs(path: str) -> RecordSet:
    """Reads a file and generates a record set from it.

    :param path: File path
    :type path: str
    :raises Exception: Issues reading the file, e.g. an invalid line.
    :return: Records of CSV file parsed into a record set.
    :rtype: [type]
    """
    recs = []

    with open(path, newline='') as f:
        reader = csv.reader(f, delimiter=',')
        for r in reader:
            if not len(r) == 3:
                raise Exception(f"Invalid record in line {reader.line_num}.")

            rec = Record.deserialize(*r)
            recs.append(rec)

    return recs


def write_recs(recs: Iterable[Iterable], path: str):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerows(recs)


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

    # TODO: Make workdate configurable with a CLI option
    workdate = date.today()

    path = os.path.join(
        cfg.get('database.directory'),
        f"{workdate.isoformat()}.csv",
    )

    # TODO: Add git pull

    log.debug(f"Touching {path}...")
    os.makedirs(Path(path).parent, exist_ok=True)
    Path(path).touch(exist_ok=True)
    log.debug(f"Touched {path}")

    log.debug("Loading file...")
    recs = RecordSet(read_recs(path))
    log.debug(f"Loaded {recs.size} records from file.")

    try:
        cmd = args.cmd[0]

        if cmd == "reset":
            recs.reset_rec()
        elif cmd == "restart":
            recs.restart_rec()
        elif cmd == "start":
            if not args.tags:
                tags = {'default'}
            else:
                tags = set(args.tags[0].split(','))
            recs.start_rec(tags)
        elif cmd == "stats":
            # TODO: Add more options, e.g:
            #         * output format (hours, minutes)
            stats = recs.generate_stats()
            output = format_stats(workdate, stats)
            log.info(output)

        elif cmd == "stop":
            recs.stop_rec()
        else:
            raise ValueError(f"Unknown command '{cmd}'")

        log.debug("Successfully executed command")
    except IllegalOperation as e:
        log.error(f"Illegal command: {str(e)}")
        log.debug("Details: ", exc_info=e)
        return

    if cmd in ['reset', 'restart', 'start', 'stop']:
        try:
            log.debug("Serializing records...")
            recs = [r.serialize() for r in recs.get_all()]
            log.debug(f"Serialized {len(recs)} records.")
            log.debug("Writing records to file.")
            write_recs(recs, path)
            log.debug("Successfully wrote records to file.")
        except Exception as e:
            log.error("Failed to write to file.")
            log.debug("Details: ", exc_info=e)

    # TODO: Add git push


if __name__ == "__main__":
    main()
