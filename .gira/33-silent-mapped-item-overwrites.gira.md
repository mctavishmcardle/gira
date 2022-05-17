TODO

# BUG: Silent mapped item overwrites

currently:
* a ticket with multiple relationships to the same ticket will only have the last
  one recorded or displayed
    * all previous labels are lost
* a ticket with multiple sections with the same name will only have the contents
  of the last one displayed
