import boto3


def remove_dia(s):
    """
    Remove diacritic marks from string.

    Based on code at https://gist.github.com/j4mie/557354,
    last access 10/28/2018.
    """
    import unicodedata
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')


polly = boto3.client('polly')

voices = polly.describe_voices()['Voices']

# NOTE: this includes diacritics that you must replace manually

voices = [(voice['Name'], voice['LanguageName']) for voice in voices]
voices = sorted(voices, key=lambda x: x[1])

template_str = '<option value="{nameval}">{name} {lang}</option>'
for voice in voices:
    print(template_str.format(nameval=remove_dia(voice[0]),
                              name=voice[0], lang=voice[1]))
