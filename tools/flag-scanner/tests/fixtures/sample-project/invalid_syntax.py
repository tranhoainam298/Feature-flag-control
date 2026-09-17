# This file has deliberately broken Python syntax to test resilience

def broken_syntax(:::
    print "missing parens and invalid syntax"
    client.is_enabled("should-not-crash-scanner")
