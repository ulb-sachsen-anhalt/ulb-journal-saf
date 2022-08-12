import inspect

# Add your custom filters here
# All functions need to follow the scheme:

# def <your_function_name>(k, value)
#   if k == "<Metadata you want to filter>"
#       <Your filtering here>
#   return value

# k will be the metadata you want to assign (dc.title, ...) in config_meta
# value will be what was parsed from the submission

# All functions in this file will be called automatically

# Example: Remove abstracts that are too short (<20 symbols):

# def filter_abstract(k, value):
#     if k == "dc.description.abstract":
#         new_value = {}
#         for lang in value:
#             if len(value[lang])>=20:
#                 new_value[lang] = value[lang]
#         value = new_value
#     return value


def your_function_name(k, value):
    if k == "Metadata_you_want_to_filter":
        pass  # Change "value" to your likings
    return value


# Begin of Custom ULB functions:

def filter_abstract(k, value):  # Filters abstracts that are too short
    if k == "dc.description.abstract":
        new_value = {}
        for lang in value:
            if len(value[lang]) >= 20:
                new_value[lang] = value[lang]
        value = new_value
    return value


def filter_author(k, value):  # Filters authors with the name "admin" or "."
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
            for bad_name in list_of_unwanted_names::
                if bad_name == cur_name:
                    del new_value[0]['givenName'][lang]
                    break
        value = new_value
    return value
# End of Custom Ulb Functions


# Do not edit below this line
# ---------------------------

def filter_metadata(k, value, filter_functions):
    for (sfun, func) in filter_functions:
        if (sfun != inspect.currentframe().f_code.co_name):  # No recursion
            value = func(k, value)
    return value