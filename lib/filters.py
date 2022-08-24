import inspect
import re
# Add your custom filters here
# All functions need to follow the scheme:

# def <your_function_name>(k, value)
#   if k == "<Metadata you want to filter>"
#       <Your filtering here>
#   return value

# k will be the metadata you want to assign (dc.title, ...) in config_meta
# value will be what was parsed from the submission
# The returned "value" needs to be the same format as the original

# All functions in this file will be called automatically

# The function name should start with _X_ , where X is a number
# Functions will be used from the lowest number to the highest (alphabetically)

# Example filter: Remove abstracts that are too short (<40 symbols):

# def _1_filter_abstract(k, value):
#     if k == "dc.description.abstract":  # Metadatum will be the abstract
#         new_value = {}  # New dict to keep the same "value" format
#         for lang in value:
#             if len(value[lang])>=40:  # Found abstract is long enough
#                new_value[lang] = value[lang]  # Keep the found abstract
#         value = new_value  # Replace value with new dict
#     return value  # Only the abstracts with >40 symbols will be returned

# Live example


def _0_your_function_name(k, value):
    if k == "Metadata_you_want_to_filter":
        pass  # Change "value" to your likings
    return value


# Begin of Custom ULB functions:
def _1_filter_author(k, value):  # Filter authors with the name "admin" or "."
    if k == "dc.contributor.author":
        list_of_unwanted_names = ["admin", "."]
        new_value = value
        for lang in list(value[0]['familyName'].keys()):
            cur_name = value[0]['familyName'][lang]
            for bad_name in list_of_unwanted_names:
                if bad_name == cur_name:
                    del new_value[0]['familyName'][lang]
                    break
        for lang in list(value[0]['givenName'].keys()):
            cur_name = value[0]['givenName'][lang]
            for bad_name in list_of_unwanted_names:
                if bad_name == cur_name:
                    del new_value[0]['givenName'][lang]
                    break
        value = new_value
    return value


def _2_remove_html_elements(k, value):  # Remove HTML elements like <p>
    list_of_potential_html_metadata = ["dc.description.abstract",
                                       "dc.description.note"]
    if k in list_of_potential_html_metadata:
        CLEANR = re.compile('<.*?>')
        if isinstance(value, dict):
            for key in value.keys():
                value[key] = re.sub(CLEANR, '', value[key])
        else:
            value = re.sub(CLEANR, '', value)
    return value


def _3_remove_controls(k, value):  # Filter control chars that break xml
    list_of_control_chars = [""]
    list_of_control_metadata = ["dc.description.abstract",
                                "dc.title"]
    if k in list_of_control_metadata:
        for lang in value:
            for cchar in list_of_control_chars:
                value[lang] = value[lang].replace(cchar, "")
    return value


def _4_remove_spaces(k, value):  # Remove spaces and double spaces
    list_of_potential_space_metadata = ["dc.description.abstract",
                                        "dc.description.note"]
    if k in list_of_potential_space_metadata:
        if isinstance(value, dict):
            for key in value.keys():
                value[key] = value[key].replace("&nbsp;", " ")\
                                        .strip().replace("  ", " ")
        else:
            value = value.replace("&nbsp;", " ").strip().replace("  ", " ")
    return value


def _5_filter_abstract(k, value):  # Filters abstracts that are too short
    if k == "dc.description.abstract":
        new_value = {}
        for lang in value:
            if len(value[lang]) >= 40:
                new_value[lang] = value[lang]
        value = new_value
    return value


def _6_remove_double_metadata(k, value):  # eng-ger doubles
    list_of_potential_doubles = ["dc.subject",
                                 "dc.publisher",
                                 "dc.relation.ispartof",
                                 "dc.description.abstract",
                                 "dc.description.note",
                                 "dc.title",
                                 "local.bibliographicCitation.journaltitle"
                                 ]
    if k in list_of_potential_doubles:
        compare_value = value.copy()
        new_value = value.copy()
        for key in value.keys():
            for key2 in compare_value.keys():
                if key2 != key:
                    if value[key] == compare_value[key2]:
                        if key in new_value.keys() and\
                                len(new_value.keys()) > 1:
                            del new_value[key]
        value = new_value
    return value
# End of Custom ULB Functions


# Do not edit below this line
# ---------------------------

def filter_metadata(k, value, filter_functions):
    for (sfun, func) in filter_functions:
        if (sfun != inspect.currentframe().f_code.co_name):  # No recursion
            value = func(k, value)
    return value
