TODO

# FEATURE: Better help text for enums

Need to work out a way to show enum options for the params that take them in & also show explanatory info on enum elements in CLI help text

# thoughts


* diplaying enum member meanings
    * should be visible in the CLI
    * will need to maintain some map of member:meaning help text
        * docstring or something on class itself?
        * the enum member values?
    * options
        * figure out a way to automatically extend the help text of commands that
          use them to show the full list of params automatically?
        * only include them in man pages or something?
            * would need to generate man pages ...
        * show them in help text if some verbosity flag is passed?
        * have a specific help flag that displays them?
* enum member metavars
    * in new, the `--status` flag shows the list of options, but the `--relationship`
      one just shows `CHOICE`, because tuples just show their element type names
        * can override `Tuple.name` or `Choice.name`, but displaying the full
          list for relationships seems bad, especially since there'll likely be
          lots of them & wrapping will probably be an issue
        * means the list of options for at least some of the enums will be in the
          above member:meaning info section
    * should all choices be displayed consistently?
        * convenient to show the full list, when it's small
            * e.g. for ticket statuses - at least for now, since there aren't
              that many
        * but nice to have full consistency
        * will need to have a cross-reference thing with the member:meaning map
          for at least some of the enums, so see how it looks there & make it
          consistent for them all if it's not too bad?
            * can have a `Choice` subclass that overrides or something


[noticed during]: 7 (CAUSED_BY)
