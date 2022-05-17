TODO

# Preserve the contents of existing files

Can do this by adding the file contents as a property on the ticket (or have it save the full path & open it when needed? is that necessary? we already only open lazily) and populating status, title, etc from that when requested. Can look for `MISSING` on dataclass


[will get no flattening for free]: 11 (FIXES)
[normalization will no longer happen for free]: 22 (RELATES_TO)
[apparent dup of 22]: 28 (RELATES_TO)
