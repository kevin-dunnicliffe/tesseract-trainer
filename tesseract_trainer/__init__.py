"""
A small training framework for Tesseract 3.0.1, taking over the tedious manual process
of training Tesseract 3described in the Tesseract Wiki:
https://code.google.com/p/tesseract-ocr/wiki/TrainingTesseract3
"""

__version__ = '0.1.1'
__author__ = 'Balthazar Rouberol, rouberol.b@gmail.com'

import shutil
import os
import subprocess
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import glob

from os.path import join, exists


# list of files generated during the training procedure
GENERATED_DURING_TRAINING = ['unicharset', 'pffmtable', 'Microfeat', 'inttemp', 'normproto']

FONT_SIZE = 25  # Default font size, used during tif generation
EXP_NUMBER = 0  # Default experience number, used in generated files name
TESSDATA_PATH = '/usr/share/tessdata'  # Default path to the 'tessdata' directory
WORD_LIST = None  # Default path to the "word_list" file, contaning frequent words
VERBOSE = True  # verbosity enabled by default. Set to False to remove all text outputs



class MultiPageTif(object):
    """ A class allowing generation of a multi-page tif. """

    def __init__(self, text, W, H, start_x, start_y, font_name, font_path, fontsize, exp_number, dictionary_name, verbose):

        # Width of the generated tifs (in px)
        self.W = W

        # Height of the generated tifs (in px)
        self.H = H

        # X coordinate of the first letter of the page
        self.start_x = start_x

        # Y coordinate of the first letter of the page
        self.start_y = start_y

        # Text to be written in generated multipage tif
        self.text = [word for word in text.split(' ')]  # utf-8 characters support

        # Font used when "writing" the text into the tif
        self.font = ImageFont.truetype(font_path, fontsize)

        # Name of the font, used for generating the file prefix
        self.font_name = font_name

        # Name of the tesseract dictionary to be generated. Used for generating the file prefix.
        self.dictionary_name = dictionary_name

        # Prefix of the generated multi-page tif file
        self.prefix = ".".join([dictionary_name, font_name, "exp" + str(exp_number)])

        # A list of boxfile lines, each one of the form "char x0 y x1 y1 page_number"
        self.boxlines = []

        # prefix of all temporary single-page tif files
        self.indiv_page_prefix = 'page'

        # Set verbose to True to display output
        self.verbose = verbose

    def generate_tif(self):
        """ Create several individual tifs from text and merge them
            into a multi-page tif, and finally delete all individual tifs.
        """
        self._fill_pages()
        self._multipage_tif()
        self._clean()

    def generate_boxfile(self):
        """ Generate a boxfile from the multipage tif.
            The boxfile will be named {self.prefix}.box
        """
        boxfile_path = self.prefix + '.box'
        if self.verbose:
            print("Generating boxfile %s" % (boxfile_path))
        with open(boxfile_path, 'w') as boxfile:
            for boxline in self.boxlines:
                boxfile.write(boxline + '\n')  # utf-8 characters support

    def _new_tif(self, color="white"):
        """ Create and returns a new RGB blank tif, with specified background color (default: white) """
        return Image.new("L", (self.W, self.H), color=color)

    def _save_tif(self, tif, page_number):
        """ Save the argument tif using 'page_number' argument in filename.
            The filepath will be {self.indiv_page_prefix}{self.page_number}.tif
        """
        tif.save(self.indiv_page_prefix + str(page_number) + '.tif')

    def _fill_pages(self):
        """ Fill individual tifs with text, and save them to disk.
            Each time a character is written in the tif, its coordinates will be added to the self.boxlines
            list (with the exception of white spaces).

            All along the process, we manage to contain the text within the image limits.
        """
        tif = self._new_tif()
        draw = ImageDraw.Draw(tif)
        page_nb = 0
        x_pos = self.start_x
        y_pos = self.start_y
        if self.verbose:
            print('Generating individual tif image %s' % (self.indiv_page_prefix + str(page_nb) + '.tif'))
        for word in self.text:
            word += ' '  # add a space between each word
            wordsize_w, wordsize_h = self.font.getsize(word)
            wordsize_w  = len(word) * 28
            wordsize_h  = 28
            # Check if word can fit the line, if not, newline
            # if newline, check if the newline fits the page
            # if not, save the current page and create a new one
            if not word_fits_in_line(self.W, x_pos, wordsize_w):
                if newline_fits_in_page(self.H, y_pos, wordsize_h):
                    # newline
                    x_pos = self.start_x
                    y_pos += wordsize_h
                else:
                    # newline AND newpage
                    x_pos = self.start_x
                    y_pos = self.start_y
                    self._save_tif(tif, page_nb)  # save individual tif
                    page_nb += 1
                    if self.verbose:
                        print('Generating individual tif image %s' % (self.indiv_page_prefix + str(page_nb) + '.tif'))
                    tif = self._new_tif()  # new page
                    draw = ImageDraw.Draw(tif)  # write on this new page
            # write word
            for char in word:
                char_w, char_h = self.font.getsize(char)  # get character height / width
                char_w = 28
                char_h = 28
                char_x0, char_y0 = x_pos, y_pos  # character top-left corner coordinates
                char_x1, char_y1 = x_pos + char_w, y_pos + char_h  # character bottom-roght corner coordinates
                draw.text((x_pos, y_pos), char, fill="black", font=self.font)  # write character in tif file
                if char != ' ':
                    # draw.rectangle([(char_x0, char_y0),(char_x1, char_y1)], outline="red")
                    self._write_boxline(char, char_x0, char_y0, char_x1, char_y1, page_nb)  # add coordinates to boxfile
                x_pos += char_w
        self._save_tif(tif, page_nb)  # save last tif

    def _write_boxline(self, char, char_x0, char_y0, char_x1, char_y1, page_nb):
        """ Generate a boxfile line given a character coordinates, and append it to the
            self.boxlines list.
        """
        # top-left corner coordinates in tesseract particular frame
        tess_char_x0, tess_char_y0 = pil_coord_to_tesseract(char_x0, char_y0, self.H)
        # bottom-right corner coordinates in tessseract particular frame
        tess_char_x1, tess_char_y1 = pil_coord_to_tesseract(char_x1, char_y1, self.H)
        boxline = '%s %d %d %d %d %d' % (char, tess_char_x0, tess_char_y1, tess_char_x1, tess_char_y0, page_nb)
        self.boxlines.append(boxline)

    def _multipage_tif(self):
        """ Generate a multipage tif from all the generated tifs.
            The multipage tif will be named {self.prefix}.tif
        """
        cmd = ['convert']  # ImageMagick command `convert` can merge individual tifs into a multipage tif file
        tifs = sorted(glob.glob(self.indiv_page_prefix + '*.tif'), key=os.path.getmtime)
        cmd.extend(tifs)  # add all individual tifs as arguments
        multitif_name = self.prefix + '.tif'
        cmd.append(multitif_name)  # name of the result multipage tif
        if self.verbose:
            print('Generating multipage-tif %s' % (multitif_name))
        subprocess.call(cmd)  # merge of all individul tifs into a multipage one

    def _clean(self):
        """ Remove all generated individual tifs """
        if self.verbose:
            print("Removing all individual tif images")
        tifs = glob.glob('%s*' % (self.indiv_page_prefix))  # all individual tifd
        for tif in tifs:
            os.remove(tif)


# Utility functions
def word_fits_in_line(pagewidth, x_pos, wordsize_w):
    """ Return True if a word can fit into a line. """
    return (pagewidth - x_pos - wordsize_w) > 0


def newline_fits_in_page(pageheight, y_pos, wordsize_h):
    """ Return True if a new line can be contained in a page. """
    return (pageheight - y_pos - (2 * wordsize_h)) > 0


def pil_coord_to_tesseract(pil_x, pil_y, tif_h):
    """ Convert PIL coordinates into Tesseract boxfile coordinates:
        in PIL, (0,0) is at the top left corner and
        in tesseract boxfile format, (0,0) is at the bottom left corner.
    """
    return pil_x, tif_h - pil_y

class TesseractTrainer:
    """ Object handling the training process of tesseract """

    def __init__(self,
        dictionary_name,
        text,
        font_name,
        font_path,
        font_properties,
        font_size=FONT_SIZE,
        exp_number=EXP_NUMBER,
        tessdata_path=TESSDATA_PATH,
        word_list=WORD_LIST,
        verbose=VERBOSE):

        # Training text: the text used for the multipage tif generation
        # we replace all \n by " " as we'll split the text over " "s
        self.training_text = open(text).read().replace("\n", " ")

        # Experience number: naming convention defined in the Tesseract training wiki
        self.exp_number = exp_number

        # The name of the result Tesseract "dictionary", trained on a new language/font
        self.dictionary_name = dictionary_name

        # The name of the font you're training tesseract on.
        # WARNING: this name must match a font name in the font_properties file
        # and must not contain spaces
        self.font_name = font_name
        if ' ' in self.font_name:
            raise SystemExit("The --font-name / -F argument must not contain any spaces. Aborting.")

        # The local path to the TrueType/OpentType file of the training font
        self.font_path = font_path
        if not exists(self.font_path):
            raise SystemExit("The %s file does not exist. Aborting." % (self.font_path))

        # The font size (in px) used during the multipage tif generation
        self.font_size = font_size

        # The prefix of all generated tifs, boxfiles, training files (ex: eng.helveticanarrow.exp0.box)
        self.prefix = '%s.%s.exp%s' % (self.dictionary_name, self.font_name, str(self.exp_number))

        # Local path to the 'font_propperties' file
        self.font_properties = font_properties
        with open(self.font_properties, 'r') as fp:
            if self.font_name not in fp.read().split():
                raise SystemExit("The font properties of %s have not been defined in %s. Aborting." % (self.font_name, self.font_properties))

        # Local path to the 'tessdata' directory
        self.tessdata_path = tessdata_path
        if not exists(self.tessdata_path):
            raise SystemExit("The %s directory does not exist. Aborting." % (self.tessdata_path))

        # Local path to a file containing frequently encountered words
        self.word_list = word_list

        # Set verbose to True to display the training commands output
        self.verbose = verbose

    def _generate_boxfile(self):
        """ Generate a multipage tif, filled with the training text and generate a boxfile
            from the coordinates of the characters inside it
        """
        mp = MultiPageTif(self.training_text, 3500, 1024, 20, 20, self.font_name, self.font_path,
            self.font_size, self.exp_number, self.dictionary_name, self.verbose)
        mp.generate_tif()  # generate a multi-page tif, filled with self.training_text
        mp.generate_boxfile()  # generate the boxfile, associated with the generated tif

    def _train_on_boxfile(self):
        """ Run tesseract on training mode, using the generated boxfiles """
        cmd = 'tesseract -psm 5 {prefix}.tif {prefix} nobatch box.train'.format(prefix=self.prefix)
        print(cmd)
        run = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        display_output(run, self.verbose)

    def _compute_character_set(self):
        """ Computes the character properties set: isalpha, isdigit, isupper, islower, ispunctuation
            and encode it in the 'unicharset' data file

            examples:
            ';' is an punctuation character. Its properties are thus represented
                by the binary number 10000 (10 in hexadecimal).
            'b' is an alphabetic character and a lower case character.
                Its properties are thus represented by the binary number 00011 (3 in hexadecimal).
            W' is an alphabetic character and an upper case character. Its properties are
                thus represented by the binary number 00101 (5 in hexadecimal).
            '7' is just a digit. Its properties are thus represented by the binary number 01000 (8 in hexadecimal).
            '=' does is not punctuation not digit or alphabetic character. Its properties
                 are thus represented by the binary number 00000 (0 in hexadecimal).
        """
        cmd = 'unicharset_extractor %s.box' % (self.prefix)
        run = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        display_output(run, self.verbose)

    def _clustering(self):
        """ Cluster character features from all the training pages, and create characters prototype """
        cmd = 'mftraining -F font_properties -U unicharset %s.tr' % (self.prefix)
        run = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        display_output(run, self.verbose)

    def _normalize(self):
        """ Generate the 'normproto' data file (the character normalization sensitivity prototypes) """
        cmd = 'cntraining %s.tr' % (self.prefix)
        run = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        display_output(run, self.verbose)

    def _rename_files(self):
        """ Add the self.dictionary_name prefix to each file generated during the tesseract training process """
        for generated_file in GENERATED_DURING_TRAINING:
            os.rename('%s' % (generated_file), '%s.%s' % (self.dictionary_name, generated_file))

    def _dictionary_data(self):
        """ Generate dictionaries, coded as a Directed Acyclic Word Graph (DAWG),
            from the list of frequent words if those were submitted during the Trainer initialization.
        """
        if self.word_list:
            cmd = 'wordlist2dawg %s %s.freq-dawg %s.unicharset' % (self.word_list, self.dictionary_name,
                self.dictionary_name)
            run = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            display_output(run, self.verbose)

    def _combine_data(self):
        cmd = 'combine_tessdata %s.' % (self.dictionary_name)
        run = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        display_output(run, self.verbose)

    def training(self):
        """ Execute all training steps """
        self._generate_boxfile()
        self._train_on_boxfile()
        self._compute_character_set()
        self._clustering()
        self._normalize()
        self._rename_files()
        self._dictionary_data()
        self._combine_data()
        if self.verbose:
            print('The %s.traineddata file has been generated !' % (self.dictionary_name))

    def clean(self):
        """ Remove all files generated during tesseract training process """
        if self.verbose:
            print('cleaning...')
        os.remove('%s.tr' % (self.prefix))
        os.remove('%s.txt' % (self.prefix))
        os.remove('%s.box' % (self.prefix))
        os.remove('%s.inttemp' % (self.dictionary_name))
        os.remove('%s.Microfeat' % (self.dictionary_name))
        os.remove('%s.normproto' % (self.dictionary_name))
        os.remove('%s.pffmtable' % (self.dictionary_name))
        os.remove('%s.unicharset' % (self.dictionary_name))
        if self.word_list:
            os.remove('%s.freq-dawg' % (self.dictionary_name))
        os.remove('mfunicharset')

    def add_trained_data(self):
        """ Copy the newly trained data to the tessdata/ directory """
        traineddata = '%s.traineddata' % (self.dictionary_name)
        if self.verbose:
            print('Copying %s to %s.' % (traineddata, self.tessdata_path))
        try:
            shutil.copyfile(traineddata, join(self.tessdata_path, traineddata))  # Copy traineddata fie to the tessdata dir
        except IOError:
            raise IOError("Permission denied. Super-user rights are required to copy %s to %s." % (traineddata, self.tessdata_path))


def display_output(run, verbose):
    """ Display the output/error of a subprocess.Popen object
        if 'verbose' is True.
    """
    out, err = run.communicate()
    if verbose:
        print(out.strip())
        if err:
            print(err.strip())
