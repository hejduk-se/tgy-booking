# tullinge/booking
# https://github.com/tullinge/booking

# imports
import string


def character_validation(
    variable,
    allow_space=True,
    allow_punctuation=True,
    swedish=True,
    allow_newline=True,
):

    # perform characters validation against is_valid_input function
    ILLEGAL_CHARACTERS = ["<", ">", ";"]
    ALLOWED_CHARACTERS = list(string.ascii_letters) + list(string.digits)

    if allow_space:
        ALLOWED_CHARACTERS.extend(list(string.whitespace))

    if not allow_newline:
        try:
            ALLOWED_CHARACTERS.remove("\n")
        except Exception:
            pass

    if allow_punctuation:
        ALLOWED_CHARACTERS.extend(list(string.punctuation))

    if swedish:
        ALLOWED_CHARACTERS.extend(["å", "ä", "ö", "Å", "Ä", "Ö"])

    if any(x in variable for x in ILLEGAL_CHARACTERS):
        return False

    if any(x not in ALLOWED_CHARACTERS for x in variable):
        return False

    return True


# general purpose input validation
def valid_string(
    variable,
    min_length=None,
    max_length=None,
    ignore_undefined=False,
    *args,
    **kwargs,
):
    """Returns boolean whether variable is valid input or not"""

    # check if variable is defined
    if not variable and not ignore_undefined:
        return False

    # if max_length is specified, checks if string is longer than max_length
    if max_length and len(variable) > max_length:
        return False

    # if min_length is specified, checks if string is shorter than min_length
    if min_length and len(variable) < min_length:
        return False

    # character validation
    if not character_validation(variable, *args, **kwargs):
        return False

    # if all checks are successful, return True
    return True


def is_integer(variable):
    # checks if integer is actually valid
    try:
        int(variable)
    except Exception:
        return False

    return True


def valid_integer(variable, min_length=None, max_length=None):
    """Returns boolean whether variable is valid input or not"""

    # check if integer against is_integer function
    if not is_integer(variable):
        return False

    # if max_length is specified, checks if integer is longer than max_length
    if max_length and len(variable) > max_length:
        return False

    # if min_length is specified, checks if integer is shorter than min_length
    if min_length and len(variable) < min_length:
        return False

    return True


def valid_email(variable):
    """Returns boolean whether variable is valid input or not"""

    # check if variable is defined
    if not variable:
        return False

    # check that variable does not contain any illegal characters
    if not character_validation(
        variable, allow_space=False, swedish=False, allow_punctuation=True
    ):
        return False

    # check if variable is valid email
    if not "@" in variable:
        return False

    return True
