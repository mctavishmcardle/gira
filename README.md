# `gira`

`gira` is a barebones ticketing system for `git` projects.

It intends to provide basic ticket tracking functionality while:
* being flexible around the structure and contents of the tickets in question,
  and
* integrating with version control to track changes to tickets in the same repo
  that tracks changes to the code that the tickets deal with

The overall goal of `gira` and its aesthetic includes emphases on:
* command-line interaction
* the filesystem as a data store
* human-readable structured plaintext
* replicating & fixing issues in existing ticketing systems (specifically JIRA)

`gira` is early in its development; the feature roadmap is undefined (though
this repo dogfoods the tool for tracking ideas for future work: check out `.gira/`)
and features are added based on interest, need, and immediate utility.

# Features

`gira` supports:
* Creating new tickets with a variety of fields (including title, status, type,
  and description)
* Arbitrary additional content in plaintext (markdown) ticket files
* Grouping tickets together with basic filesystem folders
* Creating relationships between tickets
* Modifying the properties of existing tickets
* Searching the existing tickets based on those properties
* Checking out branches corresponding to tickets being worked on
* Staging and committing changes to ticket files (and optionally other files)

# Development

The project uses `pipenv` to manage dependencies and wrangle virtual envs.

It also provides the `lint` target in `make`, which does some basic linting.
