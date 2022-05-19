TODO

# BUG: Don't allow circular relationships

They can be created during new ticket creation or relationship addition, or by manually editing ticket files

# solutions
can prevent new circularity during:
* ticket creation
    * check if the target number is the next ticket number?
* relationship addition
        * check if the ticket number is in the filtered tickets
for the above, can raise a proper `BadParameter`

can detect circularity during `Ticket` instantiation, but can't tie the problem
to specific parameters. not too bad, however, since that covers all of the above
as a fallback, and also will detect any bad tickets during searching


[first noticed during]: 12 (CAUSED_BY)
