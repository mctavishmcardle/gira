DONE

# Parse markdown files

add support for parsing markdown files

## Subtasks

* getting info from the fields in the files
* specifying those fields at ticket creation
* modifying the contents of the fields from the cli, without editing
    * e.g. changing status

## notes

* simple parsing rules?
    * e.g. look for any header with a certain pattern & grab from there, instead
      of trying to specifically structure the doc?
    * rules
        * first paragraph should be status
        * first header should be title
            * paragraphs after that are description
        * other headings are named according to their section, and any text until
          the next heading is the ocntents?
    * followup ticket to do proper parsing
