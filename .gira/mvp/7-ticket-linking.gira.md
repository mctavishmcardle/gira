DONE

# Ticket linking

some way to store & represent links between tickets:
* inline links to files?
* specifying relationships, e.g. blocking?

# pattern

* standard markdown links?
    * reference links definitions are collected at the `Document` level, so
      they're easy to get from markodown
        * link reference definitions have:
            * link label
            * link destination (the ticket path)
            * link title
        * link references have:
            * link text
            * link label pointing to the linked ticket
    * inline links are more difficult to get (because we have to parse the full
      doc for them) but they have:
        * link destination
        * link title
        * link text
    * link semantics
        * link destination should point to the file
            * relative path or absolute path within ticket dir?
            * relative path would mean we'd have to rewrite on moves
        * link title should be link type enum member
            * default to a "RELATES" type?
        * text is whatever
        * label is whatever for references
* `#<ticket number>`, since that's already used in tickets?

# problems
* using markdown links is one-directional
    * support unidirectional relationships?
    * add `link` command to add bidirectional links?
* reference link definitions aren't shown using the markdown renderer
    * should be able to just subclass the md renderer & define `render_link_ref_def`?
* using ticket paths means you have to go back & edit them on movement
    * start with just ticket numbers
        * but that means that links can't be validated on ticket instantiation,
          because that requires that all ticket numbers be known
        * change ticket instantiation to lazy-load stuff, so it doesn't need to
          parse links until later?
            * give it a path & let it grab stuff from there?
            * link validation will still require a reference to the ticket store
    * require that they be immutable?

# implementation
* reference links for first pass, inlines as followup?
