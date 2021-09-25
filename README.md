# Python Time Log Utility

This piece of software helps you to track your time spend over the day. You can
easily start and stop new activities. An activity is defined through it's the
start timestamp, the end timestamp and a set of tags.

The software creates a file-based database. As a backup and synchronization
option I simply chose git. It was the cheapest and simplest solution to keep the
database in sync over multiple devices. `tl` creates a new file for each day of
recordings. This ensures fast read and write access even if the software is used
over years and consists of tens of thousands of entries.

## Usage

**Start a recording:**

To start a recording, simply type the following command:

```
tl start -t add,some,tags
```

The flag `-t` defines a list of tags. These need to be comma separated. Spaces
are not allowed. Tags are supposed to assign certain amount of time to different
activities. A tag should just be a memory aid to give you a hint to which
project or activity the recorded time belongs.


**Stop a recording:**

Just use:

```
tl stop
```

Tags are not required, since they were already defined on the start of the
recording.


**Add backdated recordings:**

You could also add recordings retrospectively. Use the tool as follows:

```
tl add -t email,linux -d 1991-08-25 --from 20:30:00 --to 20:67:08
```

The `-d` flag defines the date to which the recording belongs. The remaining
flags `--from` and `--to` define the timestamp when the activity has started and
end. The format is `HH[:MM[:SS]]`. The minutes and seconds are optional.


**Display records & statistics:**

It's as simple as that:

```
tl stats -d 1991-08-25
```

This displays a summary of the worked hours for the given workdate.


## Install

The project is available on pip:

```
pip install time-log
```

## Configuration

After the installation, you are required to configure the software. You are
required to create a small configuration file and can be copied from this
template (copied from `config.toml.dist`):

```
[database]
directory = "./recs"

[git]
enabled = false

```


`tl` reads multiple configuration files in the following order:

```
/etc/tl/config.toml
/etc/tl.toml
./config.toml
```

### Backup & Synchronization

The most probably easiest solution to sync and backup the data was to just push
the file-based database to a git repository. I would recommend to initialize a
git repository with a README explaining what the repository is about. Then you
can configure the repositories folder or one of it's subfolders as the database.
Further you can enable git, to automatically pull & push before and after each
change of recordings.


## TODOs

There are still a few features I'd like to see in the software:

[ ] Detailed start/end times of records per day
[ ] Statistics for a week, month, year
[ ] Show start date of currently active recording
[ ] Make log level configurable

