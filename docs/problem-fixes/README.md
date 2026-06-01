# Problem Fix Documentation

This folder records production/debugging problems as one file per problem.

Each problem note should include:

- what broke
- why it broke
- where the fix lives, with code line numbers
- how the fix works
- tests or test snippets that demonstrate the bug and the expected fixed behavior

## Entries

- [001 - Mobile auth accepted empty or unnormalized input fields](001-mobile-auth-required-field-validation.md)
- [002 - Mobile auth split register/login endpoints](002-mobile-auth-ambiguous-register-login-intent.md)
- [003 - Mobile auth email length bound](003-mobile-auth-email-length-bound.md)
- [004 - Mobile auth concurrent signup race](004-mobile-auth-concurrent-signup-race.md)
- [005 - Mobile auth bcrypt 72-byte truncation](005-mobile-auth-bcrypt-truncation.md)
- [006 - Mobile auth password complexity policy](006-mobile-auth-password-complexity-policy.md)
- [007 - Mobile auth rate limiting and brute-force protection](007-mobile-auth-rate-limiting-bruteforce.md)
