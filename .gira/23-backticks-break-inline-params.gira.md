TODO
# Backticks break inline params

is there a way to have quotes work? maybe just use single ones?

# Example

running:

    gira new -t TITLE -d "foo `bar` baz"

will result in the error:

    bash: bar: command not found

and the actual description will be:

    foo  baz
