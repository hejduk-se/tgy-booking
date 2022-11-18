# Changelog

This project uses the [semantic versioning convention](https://semver.org/). Make sure to include all changes in releases within this file (and references to pull requests/issues where applicable).

## next-release

- Replace `requirements.txt` with [Pipenv](https://github.com/pypa/pipenv)

## v0.1.3 (released on 2020-01-26)

### Enhancements

- Refactor: reformat HTML-templates using code formatter [prettier](https://prettier.io/) ([#67](https://github.com/tullinge/booking/pull/67)).

## v0.1.2 (released 2020-01-08)

### Enhancements

- Rewrite `Set-Cookie` HTTP header within nginx using `map`, adds the `SameSite=Strict` flag to the default Flask header [#63](https://github.com/tullinge/booking/pull/63).

### Bugs

- Replaced faulty `proxy_hide_header` with `uwsgi_hide_header` [#66](https://github.com/tullinge/booking/issues/66).

## v0.1.1 (released 2019-12-20)

### Features

- Display student answers for questions when booking an activity (on `/confirmation` page, students).

### Bugs

- Fix [#60](https://github.com/tullinge/booking/issues/60) - Correctly perform string validation on new passwords (admin password change).

### Enhancements

- Solve [LGTM.com](https://lgtm.com/projects/g/tullinge/booking/alerts/?mode=list) alerts.
- Add `required` to all HTML forms where input is required (better user experience).
- Remove unused import.

## v0.1.0 (released 2019-12-20)

- Initial release
