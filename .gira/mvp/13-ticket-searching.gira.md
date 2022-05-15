DONE

# Ticket searching

 Add command to search tickets & have things like editing & listing be sub-commands of that

# features

* search conditions
    * status
    * group
    * text field matches?
        * with regex
        * title, description
* return set size
    * some commands only make sense for things that return only a single ticket
        * add flag on sub-commands that defaults to erroring out if the size is >1?
        * e.g. starting
    * multi-ticket viable
        * move? e.g. create group
        * editing
        * listing
            * keep plain `list` command or have it always search?
