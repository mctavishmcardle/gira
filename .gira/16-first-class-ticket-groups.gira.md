TODO

# First class ticket groups

Handle groups like ordinary tickets

# features

[features described in]:8 (REFERENCES)

* ticket group attributes
    * relationships between ticket groups?
    * some sort of dir-level file with info on the ticket grouping?

# dir-level tickets

* instead of globbing, recursively iterate through subdirs
    * only enter a subdir if its name matches the 'full slug' standard
        * i.e., would work as a ticket filename, if it had a proper suffix
    * if a ticket file has the same full slug as its immediate parent directory,
      it it counts as the group ticket
    * if no group ticket exists, that's the same as an empty ticket file
        * which should be permitted
* nomenclature
    * a ticket's 'group' is its immediate parent group
    * a ticket's 'group path' is the full path under the root ticket dir
        * plain group searches only match the immediate group
        * recursive group search are on the full group path
        * use globbing in the search string to unify the two?
