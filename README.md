# Water
## Who wrote that release?

Water (aka WWTR, for "Who Wrote That Release") is a script that figures out,
given a snapshot of code and an accompanying git repository, who was the last
person to modify the code that ended up in the release.

It works by assuming we have no development history beyond the upstream
project's git repo.  One common situation is when an open source project has
gone through internal productization that involved some unknown amount of
modification, and all you have at the end is a compressed archive from a
compliance package without the git log.

Water goes line-by-line through a snapshot of code and finds the most recent
patch with an exact matching line in the git log.  It then records who authored
and committed that patch and when, and provides a summary csv.


In this way, Water uses whatever is known about the git history to infer whose
code survived productization and went into the actual release, without having
access to the productization repo itself.  This is useful for upstream
contributors who want to have a better understanding of the impact and reach of
their code.

Water uses simple criteria for matching, and at this time just looks for exact
matches.  It isn't foolproof, but given it's reconstructing an inferred history,
it should get pretty close to reality.

Water provides simple, straightforward reports to help upstream contributors
communicate their impact to downstream consumers who may not realize the extent
to which they depend upon the work of others.

### Dependencies

Water uses python3.

Water is also compatible with pypy3, which provides a major speed bump if your
system supports it.

### How to use it

You should have a release snapshot of the project, as well as a current clone of
the upstream repo. The file structure of the release snapshot must match that of
the upstream repo.

To run water, simply type:

```./water.py -r <path to cloned git repo> -s <path to snapshot of project> -o outputfile.csv```

Or, if pypy3 is available to you (and definitely check, it's worth it!) you can use:

```pypy3 water.py -r <path to cloned git repo> -s <path to snapshot of project> -o outputfile.csv```

The resulting CSV can be opened as a spreadsheet.

### Shortcomings and limitations

There is of course always a risk of false positives, where a line in the release
snapshot is erroneously matched with a line in the git repository.  To reduce
the risk of this, water only analyzes lines which (after whitespace is stripped)
are >4 characters long.  You can change the sensitivity using the -S flag.
Increasing this number decreases the chance of trivial code matches, at the
expense of ignoring perfectly valid lines of code which are shorter than the
threshold.

### I have problems and/or solutions

I welcome suggestions and improvements in the form of pull requests, and hope
this is useful to you!

Brian

