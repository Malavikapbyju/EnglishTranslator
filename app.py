from chalice import Chalice
from contextlib import closing
import os
import uuid
from tempfile import gettempdir
import boto3

app = Chalice(app_name='Translate')

# to allow use of app.log.debug below
# also means that if there is an error, instead of just getting a 500 Server error,
# you will instead get a stack trace.
# In production code, this should be set to False
app.debug = True

# remember to change this to the name of your OWN S3 bucket
BUCKET_NAME = 'polly-translate'


def upload_to_s3(filename, bucket, folder=None, public=False):
    """
    Uploads the file to the specified bucket
    :param bucket: the name of the bucket to upload to
    :param filename: the name of the file
    :param folder: optional folder to upload to
    :param public: whether to make it publicly readable
    """
    app.log.debug('Creating S3 client')
    s3 = boto3.client('s3')
    app.log.debug('Uploading to S3')
    local_filename = os.path.join(gettempdir(), filename)
    s3_name = ''
    if folder is not None:
        s3_name = '{}/{}'.format(folder, filename)
        app.log.debug('Uploading {} to {} in bucket {}'.format(local_filename, s3_name, bucket))
        s3.upload_file(local_filename,
                       bucket,
                       s3_name)
    else:
        s3_name = '{}'.format(filename)
        app.log.debug('Uploading {} to {} in bucket {}'.format(local_filename, s3_name, bucket))
        s3.upload_file(local_filename,
                       bucket,
                       s3_name)

    if public:
        app.log.debug('Changing ACL of {} in bucket {}'.format(s3_name, bucket))
        s3.put_object_acl(ACL='public-read',
                          Bucket=bucket,
                          Key=s3_name)
def translate(text, voice, BUCKET_NAME):
    client = boto3.client('translate')
    text_after_translate=client.translate_text(Text=text,SourceLanguageCode="auto",TargetLanguageCode="en")
    url=text_to_speech(text_after_translate['TranslatedText'], voice, BUCKET_NAME)
    return url,text_after_translate['TranslatedText']


def text_to_speech(text, voice, bucket, folder=None):
    """
    Uses AWS Polly to convert the given text to speech
    :param text: the text to convert
    :param voice: the voice to use
    :param bucket: the name of the S3 bucket to upload the mp3 file to.
    :param folder: the (optional) folder within the S3 bucket in which to upload the mp3 file.
    :return: the url of where to access the converted file.
    """
    # code taken from/based on
    # https://aws.amazon.com/blogs/ai/build-your-own-text-to-speech-applications-with-amazon-polly/,
    # last access 10/29/2017
    rest = text

    # Because single invocation of the polly synthesize_speech api can
    # transform text with about 1,500 characters, we are dividing the
    # post into blocks of approximately 1,000 characters.
    app.log.debug('Chunking text')
    text_blocks = []
    while len(rest) > 1100:
        begin = 0
        end = rest.find(".", 1000)

        if end == -1:
            end = rest.find(" ", 1000)

        text_block = rest[begin:end]
        rest = rest[end:]
        text_blocks.append(text_block)
    text_blocks.append(rest)
    # app.log.debug('Done chunking text {}'.format(text_blocks))

    # For each block, invoke Polly API, which will transform text into audio
    app.log.debug('Creating polly client')
    polly = boto3.client('polly')
    filename = '{}.mp3'.format(uuid.uuid4())
    for text_block in text_blocks:
        response = polly.synthesize_speech(
            OutputFormat='mp3',
            Text=text_block,
            VoiceId=voice
        )

        # Save the audio stream returned by Amazon Polly on Lambda's temp
        # directory. If there are multiple text blocks, the audio stream
        # will be combined into a single file.
        if "AudioStream" in response:
            with closing(response["AudioStream"]) as stream:
                output = os.path.join(gettempdir(), filename)
                with open(output, "ab") as file:
                    file.write(stream.read())

    # Play the audio using the platform's default player
    # import sys
    # import subprocess
    # if sys.platform == "win32":
    #     os.startfile(output)
    # else:
    #     # the following works on Mac and Linux. (Darwin = mac, xdg-open = linux).
    #     opener = "open" if sys.platform == "darwin" else "xdg-open"
    #     subprocess.call([opener, output])

    upload_to_s3(filename, bucket, folder, True)
    result = None
    if folder is not None:
        result = 'https://s3.amazonaws.com/{bucket}/{folder}/{filename}'.format(bucket=bucket, folder=folder,
                                                                                filename=filename)
    else:
        result = 'https://s3.amazonaws.com/{bucket}/{filename}'.format(bucket=bucket,
                                                                       filename=filename)

    app.log.debug('Returning URL {}'.format(result))
    return result


@app.route('/Translate', cors=True)
def Translate():
    """
    AWS Gateway API endpoint that converts text into speech
    """
    from pprint import pprint
    # pprint(app.current_request.query_params)
    text = app.current_request.query_params.get('text', None)
    voice = app.current_request.query_params.get('voice', None)
    url, text_after_translate = translate(text, voice, BUCKET_NAME)

    if text is None or voice is None:
        return {'Error': 'text and/or voice not set'}

    return {
        'text': text_after_translate,
        'voice': voice,
        'url': url
    }
