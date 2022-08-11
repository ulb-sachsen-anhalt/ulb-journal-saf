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
#         newvalue = {}
#         for lang in value:
#             if len(value[lang])>=20:
#                 newvalue[lang] = value[lang]
#         value = newvalue
#     return value


def your_function_name(k, value):
    if k == "Metadata_you_want_to_filter":
        pass  # Change "value" to your likings
    return value


# Begin of Custom ULB functions:

def filter_abstract(k, value):  # Filters abstracts that are too short
    if k == "dc.description.abstract":
        newvalue = {}
        for lang in value:
            if len(value[lang]) >= 20:
                newvalue[lang] = value[lang]
        value = newvalue
    return value


def filter_author(k, value):  # Filters authors with the name "admin" or "."
    if k == "dc.contributor.author":
        ListOfUnwantedNames = ["admin", "."]
        newvalue = value
        for lang in list(value[0]['familyName'].keys()):
            curname = value[0]['familyName'][lang]
            for BadName in ListOfUnwantedNames:
                if BadName == curname:
                    del newvalue[0]['familyName'][lang]
                    break
        for lang in list(value[0]['givenName'].keys()):
            curname = value[0]['givenName'][lang]
            for BadName in ListOfUnwantedNames:
                if BadName == curname:
                    del newvalue[0]['givenName'][lang]
                    break
        value = newvalue
    return value
# End of Custom Ulb Functions


# Do not edit below this line
# ---------------------------

def filter_metadata(k, value, filterfunctions):
    for (sfun, func) in filterfunctions:
        if (sfun != inspect.currentframe().f_code.co_name):  # No recursion
            value = func(k, value)
    return value
