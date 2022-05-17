TODO
# Parsing builds wrong path for tickets without slugs
Create a ticket with no title (so slug & filename prefix is just number); edit to add title. Subsequent lists will display wrong full slug & edit will open the wrong file.

# fix
Pass filename when parsing file - preserve that for existing ones, but generate
new filenames when creating files
