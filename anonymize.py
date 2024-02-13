#/usr/bin/env python3
# -*- coding: utf-8 -*-
#  Copyright 2024 United Kingdom Research and Innovation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# Authors:
# Franck P. Vidal


import sys
import os, shutil
from os import walk

from pathlib import Path
from typing import NoReturn

from pydicom.filereader import read_dicomdir
from pydicom import dcmread


def isDICOMDIR(fname: str) -> bool:
    '''Check if fname corresponds to the path of a DicoMDIR file

    :param fname: the file name of the file to check
    :return True fname corresponds to the path of a DicoMDIR file, Flase otherwise'''

    return fname[-len("DICOMDIR"):] == "DICOMDIR" and os.path.isfile(fname);


def anonymiseImageFile(fname: str, PatientID: str, PatientName: str, PatientBirthDate: str) -> 'pydicom.dataset.FileDataset':
    '''Open a DICOM file and anonymise it.

    :param fname: the file name of the file to anonymise
    :param PatientID: the new value of the field PatientID
    :param PatientName: the new value of the field PatientName
    :param PatientBirthDate: the new value of the field PatientBirthDate
    :return The DICOM file instance'''

    instance = dcmread(fname);

    instance.data_element("PatientID").value = PatientID;
    instance.data_element("PatientName").value = PatientName;
    instance.data_element("PatientBirthDate").value = PatientBirthDate;
    instance.data_element("InstitutionName").value = "REMOVED";
    instance.data_element("InstitutionAddress").value = "REMOVED";
    instance.data_element("StationName").value = "REMOVED";

    if (0x0008, 0x0090) in instance:
        instance[0x0008, 0x0090].value = 'REMOVED';

    if (0x0008, 0x1048) in instance:
        instance[0x0008, 0x1048].value = 'REMOVED';

    if (0x0032, 0x1032) in instance:
        instance[0x0032, 0x1032].value = 'REMOVED';

    return instance;


def anonymiseDICOMDIR(fname: str, output_path:str) -> 'pydicom.dicomdir.DicomDir':
    '''Open a DICOMDIR file, anonymise it, and anonymise all the corresponding image files.

    :param fname: the file name of the DICOMDIR file to anonymise
    :param output_path: the output directory where the anonymised image files will be saved. Note that the directory tree will be preserved
    :return The DICOMDIR file instance'''

    # Load the DICOMDIR file
    dicom_dir = read_dicomdir(fname);
    dicomdir_dirname, fname = os.path.split(fname);

    # Iterate through the PATIENT records
    for i, dicomdir_patient in enumerate(dicom_dir.patient_records):

        old_ID = dicomdir_patient.PatientID;
        old_name = dicomdir_patient.PatientName;
        old_dob = dicomdir_patient.PatientBirthDate;

        if len(dicom_dir.patient_records) > 1:
            new_ID = "REMOVED - " + str(i)
            new_name = "REMOVED - " + str(i)
        else:
            new_ID = "REMOVED"
            new_name = "REMOVED"
        
        new_dob = "99991231"

        dicomdir_patient.data_element("PatientID").value = new_ID;
        dicomdir_patient.data_element("PatientName").value = new_name;
        dicomdir_patient.data_element("PatientBirthDate").value = new_dob;

        # Find all the STUDY records for the patient
        studies = [ii for ii in dicomdir_patient.children if ii.DirectoryRecordType == "STUDY"];

        # Process every study
        for study in studies:

            # Find all the SERIES records in the study
            all_series = [ii for ii in study.children if ii.DirectoryRecordType == "SERIES"];

            # Process every series
            for series in all_series:

                # Find all the IMAGE records in the series
                images = [ii for ii in series.children if ii.DirectoryRecordType == "IMAGE"];

                # Get the absolute file path to each instance
                #   Each IMAGE contains a relative file path to the root directory
                elems = [ii["ReferencedFileID"] for ii in images];

                # Make sure the relative file path is always a list of str
                paths = [[ee.value] if ee.VM == 1 else ee.value for ee in elems];
                paths = [Path(*p) for p in paths];

                # List the instance file paths
                for p in paths:

                    # Create the output directory
                    dirname, fname = os.path.split(p);
                    output_image_directory = os.path.join(output_path, dirname);
                    os.makedirs(output_image_directory, exist_ok=True);


                    # Read the corresponding SOP Instance
                    input_image_filename = os.path.join(dicomdir_dirname, dirname, fname);
                    if os.path.isfile(input_image_filename):

                        # Open the file and anonymise it
                        instance = anonymiseImageFile(input_image_filename, new_ID, new_name, new_dob);

                        # Save anonymised file
                        output_image_filename = os.path.join(output_image_directory, fname);
                        instance.save_as(output_image_filename);

    return dicom_dir;


def anonymiseDirectory(fname:str, output_path:str) -> NoReturn:
    '''Anonymise all the image files contained in a directory.

    :param fname: the file name of the directory to process
    :param output_path: the output directory where the anonymised image files will be saved. Note that the directory tree will be preserved'''

    # Process the directory and its subdirectories    
    for (dirpath, dirnames, filenames) in walk(fname):

        # Process all the subdirectories with files in them
        if len(filenames) > 0 and len(dirnames) == 0:

            # Create the output directory
            output_image_directory = os.path.join(output_path, os.path.relpath(dirpath, fname));
            os.makedirs(output_image_directory, exist_ok=True);

            # Process all the files
            for image_filename in filenames:
                input_image_filename = os.path.join(dirpath, image_filename);
            
                # Open the file and anonymise it
                instance = anonymiseImageFile(input_image_filename, "REMOVED", "REMOVED", "99991231");

                # Save anonymised file
                output_image_filename = os.path.join(output_image_directory, image_filename);
                instance.save_as(output_image_filename);


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: python "
            + __file__
            + " <input_directory_with_DICOM_series> <output_directory>"
        );
        sys.exit(1);

    # Save the paths
    input_path = sys.argv[1];
    output_path = sys.argv[2];

    # Error checking first
    if not os.path.exists(input_path):
        raise IOError(input_path + " does not exists.");

    if os.path.exists(output_path):
        if not os.path.isdir(output_path):
            raise IOError(output_path + " exists but it is not a directory.");
        else:
            shutil.rmtree(output_path);

    # Create the output directory
    os.makedirs(output_path, exist_ok=True);

    # The input is a DICOMDIR file
    if isDICOMDIR(input_path) and os.path.isfile(input_path):
        print(input_path, "is a DICOMDIR file")
        dicom_dir = anonymiseDICOMDIR(input_path, output_path);

        # Save the DICOMDIR file
        output_filename = f"{output_path}/DICOMDIR";
        dicom_dir.save_as(output_filename);
    
    # The input is a directory with a DICOMDIR file
    elif os.path.isdir(input_path) and isDICOMDIR(os.path.join(input_path, "DICOMDIR")):
        print(input_path, "is a directory with a DICOMDIR file")
        dicom_dir = anonymiseDICOMDIR(os.path.join(input_path, "DICOMDIR"), output_path);
    
        # Save the DICOMDIR file
        output_filename = f"{output_path}/DICOMDIR";
        dicom_dir.save_as(output_filename);

    # The input is a directory without a DICOMDIR file
    elif os.path.isdir(input_path) and not isDICOMDIR(os.path.join(input_path, "DICOMDIR")):
        print(input_path, "is a directory without a DICOMDIR file")
        anonymiseDirectory(input_path, output_path);
    
    # The input is a DICOM file
    elif os.path.isfile(input_path):
        print(input_path, "is a DICOM file")

        # Open the file and anonymise it
        instance = anonymiseImageFile(input_path, "REMOVED", "REMOVED", "99991231");

        # Save anonymised file
        instance.save_as(output_path);
    
    # The input cannot be processed
    else:
        raise IOError(input_path + " exists but it is not a DICOMDIR file, nor a directory with DICOM image files.");

    return 0

if __name__ == '__main__':
    sys.exit(main())  # next section explains the use of sys.exit
