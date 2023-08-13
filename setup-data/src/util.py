import re

def slugify(slug_, dot_comma_replacement='', misc_replacement=''):
    slug_ = re.sub(r'\.|,', dot_comma_replacement, slug_)
    slug_ = re.sub(r'[^a-øA-Ø0-9]', misc_replacement, slug_)
    return slug_