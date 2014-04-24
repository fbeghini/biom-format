#!/usr/bin/env python

# -----------------------------------------------------------------------------
# Copyright (c) 2011-2013, The BIOM Format Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# -----------------------------------------------------------------------------

from __future__ import division
import json
from datetime import datetime
from operator import and_
from functools import reduce
from pyqi.core.command import (Command, CommandIn, CommandOut,
                               ParameterCollection)
from biom.util import HAVE_H5PY, biom_open


__author__ = "Daniel McDonald"
__copyright__ = "Copyright 2011-2013, The BIOM Format Development Team"
__credits__ = ["Daniel McDonald", "Jose Clemente", "Greg Caporaso",
               "Jai Ram Rideout", "Justin Kuczynski", "Andreas Wilke",
               "Tobias Paczian", "Rob Knight", "Folker Meyer", "Sue Huse"]
__license__ = "BSD"
__url__ = "http://biom-format.org"
__author__ = "Daniel McDonald"
__email__ = "daniel.mcdonald@colorado.edu"


class TableValidator(Command):
    BriefDescription = "Validate a BIOM-formatted file"
    LongDescription = ("Test a file for adherence to the Biological "
                       "Observation Matrix (BIOM) format specification. This "
                       "specification is defined at http://biom-format.org")

    CommandIns = ParameterCollection([
        CommandIn(Name='table', DataType=object,
                  Description='the input BIOM JSON object (e.g., the output '
                  'of json.load)', Required=True),
        CommandIn(Name='is_json', DataType=bool,
                  Description='the input type',
                  Required=False, Default=False),
        CommandIn(Name='format_version', DataType=str,
                  Description='the specific format version to validate '
                  'against', Required=False,
                  Default='1.0.0'),
        CommandIn(Name='detailed_report', DataType=bool,
                  Description='include more details in the output report',
                  Required=False, Default=False)
    ])

    CommandOuts = ParameterCollection([
        CommandOut(Name='valid_table',
                   Description='Is the table valid?',
                   DataType=bool),
        CommandOut(Name='report_lines',
                   Description='Detailed report',
                   DataType=list)
    ])

    FormatURL = "http://biom-format.org"
    TableTypes = set(['otu table', 'pathway table', 'function table',
                      'ortholog table', 'gene table', 'metabolite table',
                      'taxon table'])
    MatrixTypes = set(['sparse', 'dense'])
    ElementTypes = {'int': int, 'str': str, 'float': float, 'unicode': unicode}
    HDF5FormatVersions = set([(2, 0)])

    def run(self, **kwargs):
        is_json = kwargs['is_json']

        # this is not pyqi-appriopriate, but how we parse this thing is
        # dependent on runtime options :(
        with biom_open(kwargs['table']) as f:
            if is_json:
                kwargs['table'] = json.load(f)
                return self._validate_json(**kwargs)
            elif HAVE_H5PY:
                kwargs['table'] = f
                return self._validate_hdf5(**kwargs)
            else:
                raise IOError("h5py is not installed, can only validate JSON "
                              "tables")

    def _validate_hdf5(self, **kwargs):
        table = kwargs['table']

        # Need to make this an attribute so that we have this info during
        # validation.
        detailed_report = kwargs['detailed_report']

        report_lines = []
        valid_table = True

        if detailed_report:
            report_lines.append("Validating BIOM table...")

        required_attrs = [
            ('format-url', self._valid_format_url),
            ('format-version', self._valid_hdf5_format_version),
            ('type', self._valid_type),
            ('shape', self._valid_shape),
            ('nnz', self._valid_nnz),
            ('generated-by', self._valid_generated_by),
            ('id', self._valid_nullable_id),
            ('creation-date', self._valid_creation_date)
        ]

        required_groups = ['observation', 'sample']

        required_datasets = ['observation/ids',
                             'observation/data',
                             'observation/indices',
                             'observation/indptr',
                             'sample/ids',
                             'sample/data',
                             'sample/indices',
                             'sample/indptr']

        for key, method in required_attrs:
            if key not in table.attrs:
                valid_table = False
                report_lines.append("Missing attribute: '%s'" % key)
                continue

            if detailed_report:
                report_lines.append("Validating '%s'..." % key)

            status_msg = method(table)

            if len(status_msg) > 0:
                valid_table = False
                report_lines.append(status_msg)

        for group in required_groups:
            if group not in table:
                valid_table = False
                if detailed_report:
                    report_lines.append("Missing group: %s" % group)

        for dataset in required_datasets:
            if dataset not in table:
                valid_table = False
                if detailed_report:
                    report_lines.append("Missing dataset: %s" % dataset)

        if 'shape' in table.attrs:
            if detailed_report:
                report_lines.append("Validating 'shape' versus number of "
                                    "samples and observations...")

            n_obs, n_samp = table.attrs['shape']
            obs_ids = table.get('observation/ids', None)
            samp_ids = table.get('sample/ids', None)

            if obs_ids is None:
                valid_table = False
                report_lines.append("observation/ids does not exist, cannot "
                                    "validate shape")

            if samp_ids is None:
                valid_table = False
                report_lines.append("sample/ids does not exist, cannot "
                                    "validate shape")

            if n_obs != len(obs_ids):
                valid_table = False
                report_lines.append("Number of observation IDs is not equal "
                                    "to the described shape")

            if n_samp != len(samp_ids):
                valid_table = False
                report_lines.append("Number of sample IDs is not equal "
                                    "to the described shape")

        return {'valid_table': valid_table, 'report_lines': report_lines}

    def _validate_json(self, **kwargs):
        table_json = kwargs['table']

        # Need to make this an attribute so that we have this info during
        # validation.
        self._format_version = kwargs['format_version']
        detailed_report = kwargs['detailed_report']

        report_lines = []
        valid_table = True

        if detailed_report:
            report_lines.append("Validating BIOM table...")

        required_keys = [
            ('format', self._valid_format),
            ('format_url', self._valid_format_url),
            ('type', self._valid_type),
            ('rows', self._valid_rows),
            ('columns', self._valid_columns),
            ('shape', self._valid_shape),
            ('data', self._valid_data),
            ('matrix_type', self._valid_matrix_type),
            ('matrix_element_type', self._valid_matrix_element_type),
            ('generated_by', self._valid_generated_by),
            ('id', self._valid_nullable_id),
            ('date', self._valid_datetime)
        ]

        for key, method in required_keys:
            if key not in table_json:
                valid_table = False
                report_lines.append("Missing field: '%s'" % key)
                continue

            if detailed_report:
                report_lines.append("Validating '%s'..." % key)

            status_msg = method(table_json)

            if len(status_msg) > 0:
                valid_table = False
                report_lines.append(status_msg)

        if 'shape' in table_json:
            if detailed_report:
                report_lines.append("Validating 'shape' versus number of rows "
                                    "and columns...")

            if ('rows' in table_json and
                    len(table_json['rows']) != table_json['shape'][0]):
                valid_table = False
                report_lines.append("Number of rows in 'rows' is not equal to "
                                    "'shape'")

            if ('columns' in table_json and
                    len(table_json['columns']) != table_json['shape'][1]):
                valid_table = False
                report_lines.append("Number of columns in 'columns' is not "
                                    "equal to 'shape'")

        return {'valid_table': valid_table, 'report_lines': report_lines}

    def _json_or_hdf5_get(self, table, key):
        if hasattr(table, 'attrs'):
            return table.attrs.get(key, None)
        else:
            return table.get(key, None)

    def _json_or_hdf5_key(self, table, key):
        if hasattr(table, 'attrs'):
            return key.replace('_', '-')
        else:
            return key

    def _is_int(self, x):
        """Return True if x is an int"""
        return isinstance(x, int)

    def _valid_nnz(self, table):
        """Check if nnz seems correct"""
        if not isinstance(table.attrs['nnz'], int):
            return "nnz is not an integer!"
        if table.attrs['nnz'] < 0:
            return "nnz is negative!"
        return ''

    def _valid_format_url(self, table):
        """Check if format_url is correct"""
        key = self._json_or_hdf5_key(table, 'format_url')
        value = self._json_or_hdf5_get(table, key)

        if value != self.FormatURL:
            return "Invalid '%s'" % key
        else:
            return ''

    def _valid_shape(self, table):
        """Matrix header is (int, int) representing the size of a 2D matrix"""
        a, b = self._json_or_hdf5_get(table, 'shape')

        if not (self._is_int(a) and self._is_int(b)):
            return "'shape' values do not appear to be integers"
        else:
            return ''

    def _valid_matrix_type(self, table_json):
        """Check if a valid matrix type exists"""
        if table_json['matrix_type'] not in self.MatrixTypes:
            return "Unknown 'matrix_type'"
        else:
            return ''

    def _valid_matrix_element_type(self, table_json):
        """Check if a valid element type exists"""
        if table_json['matrix_element_type'] not in self.ElementTypes:
            return "Unknown 'matrix_element_type'"
        else:
            return ''

    def _check_date(self, val):
        valid_times = ["%Y-%m-%d",
                       "%Y-%m-%dT%H:%M",
                       "%Y-%m-%dT%H:%M:%S",
                       "%Y-%m-%dT%H:%M:%S.%f"]
        valid_time = False
        for fmt in valid_times:
            try:
                datetime.strptime(val, fmt)
                valid_time = True
                break
            except:
                pass

        if valid_time:
            return ''
        else:
            return "Timestamp does not appear to be ISO 8601"

    def _valid_creation_date(self, table):
        """Verify datetime can be parsed

        Expects ISO 8601 datetime format (for example, 2011-12-19T19:00:00
                                          note that a 'T' separates the date
                                          and time)
        """
        return self._check_date(table.attrs['creation-date'])

    def _valid_datetime(self, table):
        """Verify datetime can be parsed

        Expects ISO 8601 datetime format (for example, 2011-12-19T19:00:00
                                          note that a 'T' separates the date
                                          and time)
        """
        return self._check_date(table['date'])

    def _valid_sparse_data(self, table_json):
        """All index positions must be integers and values are of dtype"""
        dtype = self.ElementTypes[table_json['matrix_element_type']]
        n_rows, n_cols = table_json['shape']
        n_rows -= 1  # adjust for 0-based index
        n_cols -= 1  # adjust for 0-based index

        for idx, coord in enumerate(table_json['data']):
            try:
                x, y, val = coord
            except:
                return "Bad matrix entry idx %d: %s" % (idx, repr(coord))

            if not self._is_int(x) or not self._is_int(y):
                return "Bad x or y type at idx %d: %s" % (idx, repr(coord))

            if not isinstance(val, dtype):
                return "Bad value at idx %d: %s" % (idx, repr(coord))

            if x < 0 or x > n_rows:
                return "x out of bounds at idx %d: %s" % (idx, repr(coord))

            if y < 0 or y > n_cols:
                return "y out of bounds at idx %d: %s" % (idx, repr(coord))

        return ''

    def _valid_dense_data(self, table_json):
        """All elements must be of dtype and correspond to shape"""
        dtype = self.ElementTypes[table_json['matrix_element_type']]
        n_rows, n_cols = table_json['shape']

        for row in table_json['data']:
            if len(row) != n_cols:
                return "Incorrect number of cols: %s" % repr(row)

            if not reduce(and_, [isinstance(v, dtype) for v in row]):
                return "Bad datatype in row: %s" % repr(row)

        if len(table_json['data']) != n_rows:
            return "Incorrect number of rows in matrix"

        return ''

    def _valid_hdf5_format_version(self, table):
        """Format must be the expected version"""
        ver = table.attrs['format-version']
        if tuple(ver) not in self.HDF5FormatVersions:
            return "Invalid format version '%s'" % str(ver)
        else:
            return ""

    def _valid_format(self, table_json):
        """Format must be the expected version"""
        if table_json['format'] != self._format_version:
            return "Invalid format '%s', must be '%s'" % (table_json['format'],
                                                          self._format_version)
        else:
            return ''

    def _valid_type(self, table):
        """Table must be a known table type"""
        key = self._json_or_hdf5_key(table, 'type')
        value = self._json_or_hdf5_get(table, key)
        if value.lower() not in self.TableTypes:
            return "Unknown BIOM type: %s" % value
        else:
            return ''

    def _valid_generated_by(self, table):
        """Validate the generated_by field"""
        key = self._json_or_hdf5_key(table, 'generated_by')
        value = self._json_or_hdf5_get(table, key)
        if not value:
            return "'generated_by' is not populated"

        return ''

    def _valid_nullable_id(self, table_json):
        """Validate the table id"""
        # this is nullable and don't actually care what is in here
        return ''

    def _valid_id(self, record):
        """Validate id for a row or column"""
        if not record['id']:
            return "'id' in %s appears empty" % record
        else:
            return ''

    def _valid_metadata(self, record):
        """Validate the metadata field for a row or column"""
        # this is nullable and don't actually care what is in here
        if record['metadata'] is None:
            return ''
        if isinstance(record['metadata'], dict):
            return ''

        return "metadata is neither null or an object"

    def _valid_rows(self, table_json):
        """Validate the 'rows' under 'table'"""
        required_keys = [('id', self._valid_id),
                         ('metadata', self._valid_metadata)]
        required_by_type = {}
        required_keys.extend(
            required_by_type.get(table_json['type'].lower(), []))

        for idx, row in enumerate(table_json['rows']):
            for key, method in required_keys:
                if key not in row:
                    return "ROW IDX %d MISSING '%s' FIELD" % (idx, key)

                result = method(row)
                if len(result) > 0:
                    return result
        return ''

    def _valid_columns(self, table_json):
        """Validate the 'columns' under 'table'"""
        required_keys = [('id', self._valid_id),
                         ('metadata', self._valid_metadata)]
        required_by_type = {}
        required_keys.extend(
            required_by_type.get(table_json['type'].lower(), []))

        for idx, col in enumerate(table_json['columns']):
            for key, method in required_keys:
                if key not in col:
                    return "COL IDX %d MISSING '%s' FIELD" % (idx, key)

                result = method(col)
                if len(result) > 0:
                    return result
        return ''

    def _valid_data(self, table_json):
        """Validate the 'matrix' under 'table'"""
        if table_json['matrix_type'].lower() == 'sparse':
            return self._valid_sparse_data(table_json)
        elif table_json['matrix_type'].lower() == 'dense':
            return self._valid_dense_data(table_json)
        else:
            return "Unknown matrix type"

CommandConstructor = TableValidator
