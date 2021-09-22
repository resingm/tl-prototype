#!/usr/bin/env python3

import argparse
import csv
import logging
import os
import subprocess

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

import yacf
from pretty_tables import PrettyTables


# app specific constants
__version__ = (0, 1, 7)
__app__ = "tl"

# regular constants
CONFIGS = [
    '/etc/tl/config.toml',
    '/etc/tl.toml',
    './config.toml',
]

READ_ACCESS = ['stats']
WRITE_ACCESS = ['add', 'reset', 'restart', 'start', 'stop']


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

    def add_rec(self, _from: datetime, _to: datetime, tags: Set):
        """Appends a new record to the record set. Swaps with the last element
        if this is open.

        :param _from: Start time of the record
        :type _from: datetime
        :param _to: End time of the record
        :type _to: datetime
        """
        rec = Record(_from, _to, tags)

        if not self.closed:
            curr = self._recs.pop()
            self._recs.append(rec)
            self._recs.append(curr)
        else:
            self._recs.append(rec)

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
        choices=READ_ACCESS + WRITE_ACCESS,
        help="Start or close a time recording",
    )

    parser.add_argument(
        '-d',
        '--date',
        nargs='?',
        type=date.fromisoformat,
        help="Define a workdate, in YYYY-MM-DD)",
        default=date.fromisoformat(date.today().isoformat()),
    )

    parser.add_argument(
        "-t",
        "--tags",
        nargs="+",
        default="default",
    )

    parser.add_argument(
        "--git",
        action=argparse.BooleanOptionalAction,
    )

    # TODO: Consider using a subparser for the different commands, especially the <add> command
    #       https://docs.python.org/3/library/argparse.html?highlight=argparse#argparse.ArgumentParser.add_subparsers
    parser.add_argument(
        "--from",
        type=time.fromisoformat,
        help="Defines the start time when using the <add> command, in HH[:MM[:SS]]",
        dest="_from",
    )

    parser.add_argument(
        "--to",
        type=time.fromisoformat,
        help="Defines the end time when using the <add> command, in HH[:MM[:SS]]",
        dest="_to",
    )

    return parser


def format_stats(workdate: date, stats: Dict, timeformat: str = 'H', indentation: int = 4) -> str:
    """Formats statistics accordingly to the given parameters.

    :param workdate: Day to be displayed
    :type workdate: date
    :param stats: Dictionary with statistics per tag.
    :type stats: Dict
    :param timeformat: Format to print, defaults to 'H'
    :type timeformat: str, optional
    :param indentation: Indentation for each line, defaults to 4
    :type indentation: int, optional
    :return: Formatted output that can be printed or written to file.
    :rtype: str
    """
    # Highlight active recordings in the table.
    tags = list(stats.keys())
    tags.sort()
    vals = []

    for t in tags:
        v = timedelta(seconds=stats[t])
        v = v.seconds / (3600)
        vals.append(round(v, 2))

    rows = [list(x) for x in zip(tags, vals)]

    if not rows:
        rows.append([None, None])

    table = PrettyTables.generate_table(
        headers=['Tag', f'Time ({timeformat})'],
        rows=rows,
        empty_cell_placeholder='-',
    )

    # Add final polishing
    title = f"{workdate.isoformat()}"
    underline = "=" * len(title)
    lines = f"\n{title}\n{underline}\n\n{table}\n"
    lines = lines.split("\n")
    lines = map(lambda x: (" " * indentation) + x, lines)
    return "\n".join(lines)


def read_recs(path: str) -> RecordSet:
    """Reads a file and generates a record set from it.

    :param path: File path
    :type path: str
    :raises Exception: Issues reading the file, e.g. an invalid line.
    :return: Records of CSV file parsed into a record set.
    :rtype: RecordSet
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


def read_input(msg: str, of_type: Callable = str) -> Any:
    """Prints a question and requests some user input. If a 'read_as' type is
    defined, it tries to parse the value into the type and repeatedly asks for
    input, if the input is invalid.

    :param msg: Message to be prompted to the user
    :type msg: str
    :param of_type: Function to be used to parse user input, defaults to str
    :type of_type: Callable, optional
    :return: Parsed input
    :rtype: Any
    """
    msg = msg.strip(' ')

    if not msg[-1] in [':', '?']:
        msg += ':'

    inp = None

    while inp is None:
        try:
            inp = input(msg)
            inp = of_type(inp)
        except Exception:
            print(f"Invalid input. Please enter a valid '{of_type.__name__}'")
            inp = None

    return inp


def shell(*args, cwd: str = None) -> Tuple[str, str]:
    """Performs a shell command and returns the piped STDERR & STDOUT.
    Args has to be an Iterable[Iterable[str]].

    :return: Tuple of (STDOUT, STDERR)
    :rtype: Tuple[str, str]
    """
    if cwd is None:
        raise ValueError("shell() requires a working directory.")

    out, err = "", ""

    for arg in args:
        process = subprocess.run(
            arg,
            cwd=cwd,
            timeout=7,
            capture_output=True,
            text=True,
        )
        _out, _err = process.stdout, process.stderr

        if _out:
            out += _out

        if _err:
            err += _err

    return out, err


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

    # Loading configuration
    log.debug("Loading configuration...")

    _cfg = []
    for f in CONFIGS:
        if os.path.isfile(f):
            _cfg.append(f)

    cfg = yacf.Configuration(*_cfg).load().dict()
    _cfg = ":".join(_cfg)
    log.debug(f"Loaded configuration from {_cfg}")

    # postprocess configuration to include CLI options
    if args.git is not None:
        # TODO: Use yacf.configuration.set() as soon as it is available
        # cfg.get('git', {})['enabled'] = args.git
        cfg['git.enabled'] = args.git

    workdate = args.date

    path = os.path.join(
        cfg.get('database.directory'),
        f"{workdate.isoformat()}.csv",
    )

    has_write = args.cmd[0] in WRITE_ACCESS

    if cfg.get('git.enabled'):
        log.debug("Trying to pull latest changes from git.")
        out, err = shell(["git", "pull"], cwd=cfg.get('database.directory'))

        if len(err):
            log.error("'git pull' piped to STDERR:")
            list(map(log.error, err.split('\n')))
        if len(out):
            log.debug("'git pull' piped to STDOUT:")
            list(map(log.debug, out.split('\n')))

    log.debug(f"Touching {path}...")
    os.makedirs(Path(path).parent, exist_ok=True)
    Path(path).touch(exist_ok=True)
    log.debug(f"Touched {path}")

    log.debug("Loading file...")
    recs = RecordSet(read_recs(path))
    log.debug(f"Loaded {recs.size} records from file.")

    try:
        cmd = args.cmd[0]
        
        # Parse tags:
        tags = args.tags.split(',')

        if cmd == "add":
            # prepare datetime stamps for _from and _to
            _from = datetime.combine(workdate, args._from)
            _to = datetime.combine(workdate, args._to)

            if _from is None or _to is None:
                log.error("Missing arguments for the options --from and --to. Exiting...")
            else:
                recs.add_rec(_from, _to, tags)
        elif cmd == "reset":
            recs.reset_rec()
        elif cmd == "restart":
            recs.restart_rec()
        elif cmd == "start":
            #if not args.tags:
            #    tags = {'default'}
            #else:
            #    tags = set(args.tags[0].split(','))
            recs.start_rec(tags)
        elif cmd == "stats":
            # TODO: Add more options, e.g:
            #         * output format (hours, minutes)
            stats = recs.generate_stats()
            output = format_stats(workdate, stats)
            log.info(f"\n{output}")
            # print(output)

        elif cmd == "stop":
            recs.stop_rec()
        else:
            raise ValueError(f"Unknown command '{cmd}'")

        log.debug("Successfully executed command")
    except IllegalOperation as e:
        log.error(f"Illegal command: {str(e)}")
        log.debug("Details: ", exc_info=e)
        return

    if has_write:
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

    if has_write and cfg.get('git.enabled'):
        log.debug("Trying to push latest changes to git.")
        out, err = shell(
            ['git', 'add', '.'],
            ['git', 'commit', '-m', 'Autoupdate triggered by tl (https://github.com/resingm/tl-prototype)'],
            ['git', 'push'],
            cwd=cfg.get('database.directory'),
        )

        if len(err):
            log.error("Committing & pushing changes piped to STDERR:")
            list(map(log.error, err.split('\n')))
        if len(out):
            log.debug("Committing & pushing changes piped to STDOUT:")
            list(map(log.debug, out.split('\n')))


if __name__ == "__main__":
    main()
