#!/usr/bin/env python
#-*- coding: utf-8 -*-

#MODULE:     r.in.usgs
#
#AUTHOR:    Zechariah Krautwurst
#
#MENTORS:    Anna Petrasova
#            Vaclav Petras
#
#PURPOSE:    Download user-requested products through the USGS TNM API.
#
#COPYRIGHT:  (C) 2017 Zechariah Krautwurst and the GRASS Development Team
#
#            This program is free software under the GNU General Public
#            License (>=v2). Read the file COPYING that comes with GRASS
#            for details.

#%module
#% description: Download user-requested products through the USGS TNM API
#% keyword: import
#% keyword: raster
#% keyword: USGS
#% keyword: NED
#% keyword: NLCD
#%end

#%flag
#% key: i
#% label: Return USGS data information without downloading files
#% description: Return USGS data information without downloading files
#% guisection: USGS Data Selection
#%end

#%option
#% key: product
#% required: yes
#% options: ned, nlcd, naip, ustopo
#% label: USGS data product
#% description: Available USGS data products to query
#% guisection: USGS Data Selection
#%end

#%option
#% key: ned_dataset
#% required: no
#% options: 1 arc-second, 1/3 arc-second, 1/9 arc-second
#% answer: 1/3 arc-second
#% label: NED dataset
#% description: Available NED datasets to query
#% guisection: NED
#%end

#%option
#% key: nlcd_dataset
#% required: no
#% options: National Land Cover Database (NLCD) - 2001, National Land Cover Database (NLCD) - 2006, National Land Cover Database (NLCD) - 2011
#% answer: National Land Cover Database (NLCD) - 2011
#% label: NLCD dataset
#% description: Available NLCD datasets to query
#% guisection: NLCD
#%end

#%option
#% key: nlcd_subset
#% required: no
#% options: Percent Developed Imperviousness, Percent Tree Canopy, Land Cover
#% answer: Land Cover
#% label: NLCD subset
#% description: Available NLCD subsets to query
#% guisection: NLCD
#%end

#%option
#% key: naip_dataset
#% required: no
#% options: Imagery - 1 meter (NAIP)
#% answer: Imagery - 1 meter (NAIP)
#% label: NAIP dataset
#% description: Available NAIP datasets to query
#% guisection: NAIP
#%end

#%option
#% key: ustopo_dataset
#% required: no
#% options: US Topo Current, US Topo Historical
#% answer: US Topo Current
#% label: US Topo Data
#% description: Available UStopo datasets to query
#% guisection: USTopo
#%end

#%option G_OPT_M_DIR
#% key: output_directory
#% required: yes
#% description: Directory for USGS data download and processing
#% guisection: Download Options
#%end

#%option G_OPT_R_OUTPUT
#% key: output_name
#% required: yes
#% guisection: Download Options
#%end

#%option
#% key: resampling_method
#% type: string
#% required: no
#% multiple: no
#% options: default,nearest,bilinear,bicubic,lanczos,bilinear_f,bicubic_f,lanczos_f
#% description: Resampling method to use
#% descriptions: default;default method based on product;nearest;nearest neighbor;bilinear;bilinear interpolation;bicubic;bicubic interpolation;lanczos;lanczos filter;bilinear_f;bilinear interpolation with fallback;bicubic_f;bicubic interpolation with fallback;lanczos_f;lanczos filter with fallback
#% answer: default
#% guisection: Download Options
#%end

#%flag
#% key: k
#% label: Keep extracted files after GRASS import and patch
#% description: Keep extracted files after GRASS import and patch
#% guisection: Download Options
#%end

#%rules
#% required: output, -i
#%end

import sys
import os
import zipfile
import grass.script as gscript
import urllib
import urllib2
import json
import atexit

from grass.exceptions import CalledModuleError

cleanup_list = []

def main():
    # Hard-coded parameters needed for USGS datasets
    # NED and NLCD datasets fully functional
    # NAIP and UStopo not functional
    usgs_product_dict = {
        "ned":{
                'product':'National Elevation Dataset (NED)',
                'dataset':{
                        '1 arc-second': (1. / 3600, 30, 100),
                        '1/3 arc-second': (1. / 3600 / 3, 10, 30),
                        '1/9 arc-second': (1. / 3600 / 9, 3, 10)
                        },
                'subset':{},
                'extent':[
                        '1 x 1 degree',
                        '15 x 15 minute'
                         ],
                'format':'IMG',
                'extension':'img',
                'zip':True,
                'srs':'wgs84',
                'srs_proj4':"+proj=longlat +ellps=GRS80 +datum=NAD83 +nodefs",
                'interpolation':'bilinear',
                'url_split':'/'
                },
        "nlcd":{
                'product':'National Land Cover Database (NLCD)',
                'dataset':{
                        'National Land Cover Database (NLCD) - 2001': (1. / 3600, 30, 100),
                        'National Land Cover Database (NLCD) - 2006': (1. / 3600, 30, 100),
                        'National Land Cover Database (NLCD) - 2011': (1. / 3600, 30, 100)
                        },
                'subset':{
                        'Percent Developed Imperviousness',
                        'Percent Tree Canopy',
                        'Land Cover'
                        },
                'extent': ['3 x 3 degree'],
                'format':'GeoTIFF',
                'extension':'tif',
                'zip':True,
                'srs':'wgs84',
                'srs_proj4':"+proj=longlat +ellps=GRS80 +datum=NAD83 +nodefs",
                'interpolation':'nearest',
                'url_split':'&FNAME='
                },
        "naip":{
                'product':'USDA National Agriculture Imagery Program (NAIP)',
                'dataset':{
                        'Imagery - 1 meter (NAIP)': (1. / 3600 / 27, 1, 3)},
                'subset':{},
                'extent':[
                        '3.75 x 3.75 minute',
                         ],
                'format':'JPEG2000',
                'extension':'jp2',
                'zip':False,
                'srs':'wgs84',
                'srs_proj4':"+proj=longlat +ellps=GRS80 +datum=NAD83 +nodefs",
                'interpolation':'nearest',
                'url_split':'/'
                },
        "ustopo":{
            'product':'US Topo',
            'dataset':{
                    'US Topo Current':(1. / 3600 / 108, 4, 12),
                    'US Topo Historical':(1. / 3600 / 108, 4, 12)},
            'subset':{},
            'extent':['7.5 x 7.5 minute'],
            'format':'GeoPDF',
            'extension':'pdf',
            'zip':False,
            'srs':'wgs84',
            'srs_proj4':"+proj=longlat +ellps=GRS80 +datum=NAD83 +nodefs",
            'interpolation':'nearest',
            'url_split':'/'}
            }

    # Set GRASS GUI options and flags to python variables
    gui_product = options['product']

    # Variable assigned from USGS product dictionary
    nav_string = usgs_product_dict[gui_product]
    product = nav_string['product']
    product_format = nav_string['format']
    product_extension = nav_string['extension']
    product_is_zip = nav_string['zip']
    product_srs = nav_string['srs']
    product_proj4 = nav_string['srs_proj4']
    product_interpolation = nav_string['interpolation']
    product_url_split = nav_string['url_split']
    product_extent = nav_string['extent']

    # Parameter assignments for each dataset
    if gui_product == 'ned':
        gui_dataset = options['ned_dataset']
        product_tag = product + " " + gui_dataset
        gui_subset = None
    if gui_product == 'nlcd':
        gui_dataset = options['nlcd_dataset']
        product_tag = gui_dataset
        gui_subset = options['nlcd_subset']
    if gui_product == 'naip':
        gui_dataset = options['naip_dataset']
        product_tag = nav_string['product']
        gui_subset = None
    if gui_product == 'ustopo':
        gui_dataset = options['ustopo_dataset']
        product_tag = nav_string['product']
        gui_subset = None
    
    # Assigning further parameters from GUI
    gui_output_layer = options['output']
    gui_resampling_method = options['resampling_method']
    gui_i_flag = flags['i']
    gui_k_flag = flags['k']
    work_dir = options['output_directory']

    # Returns current units
    try:
        proj = gscript.parse_command('g.proj', flags='g')
        if gscript.locn_is_latlong():
            product_resolution = nav_string['dataset'][gui_dataset][0]
        elif float(proj['meters']) == 1:
            product_resolution = nav_string['dataset'][gui_dataset][1]
        else:
            # we assume feet
            product_resolution = nav_string['dataset'][gui_dataset][2]
    except TypeError:
        product_resolution = False

    if gui_resampling_method == 'default':
        gui_resampling_method = nav_string['interpolation']
        gscript.verbose(_("The default resampling method for product {product} is {res}").format(product=gui_product,
                        res=product_interpolation))

    # Get coordinates for current GRASS computational region and convert to USGS SRS
    gregion = gscript.region()
    min_coords = gscript.read_command('m.proj', coordinates=(gregion['w'], gregion['s']),
                                                proj_out=product_proj4, separator='comma',
                                                flags='d')
    max_coords = gscript.read_command('m.proj', coordinates=(gregion['e'], gregion['n']),
                                                proj_out=product_proj4, separator='comma',
                                                flags='d')
    min_list = min_coords.split(',')[:2]
    max_list = max_coords.split(',')[:2]
    list_bbox = min_list + max_list
    str_bbox = ",".join((str(coord) for coord in list_bbox))

    # Format variables for TNM API call
    gui_prod_str = str(product_tag)
    datasets = urllib.quote_plus(gui_prod_str)
    prod_format = urllib.quote_plus(product_format)
    prod_extent = urllib.quote_plus(product_extent[0])

    # Create TNM API URL
    base_TNM = "https://viewer.nationalmap.gov/tnmaccess/api/products?"
    datasets_TNM = "datasets={0}".format(datasets)
    bbox_TNM = "&bbox={0}".format(str_bbox)
    prod_format_TNM = "&prodFormats={0}".format(prod_format)
    TNM_API_URL = base_TNM + datasets_TNM + bbox_TNM + prod_format_TNM
    if gui_product == 'nlcd':
        TNM_API_URL += "&prodExtents={0}".format(prod_extent)

    gscript.verbose("TNM API Query URL:\t{0}".format(TNM_API_URL))

    # Query TNM API
    try:
        TNM_API_GET = urllib2.urlopen(TNM_API_URL, timeout=12)
    except urllib2.URLError:
        gscript.fatal("USGS TNM API query has timed out. Check network configuration. Please try again.")

    # Parse return JSON object from API query
    try:
        return_JSON = json.load(TNM_API_GET)
    except:
        gscript.fatal("Unable to load USGS JSON object.")
    
    # Functions down_list() and exist_list() used to determine 
    # existing files and those that need to be downloaded.
    
    def down_list():
        dwnld_url.append(TNM_file_URL)
        dwnld_size.append(TNM_file_size)
        TNM_file_titles.append(TNM_file_title)
        if product_is_zip:
            extract_zip_list.append(local_zip_path)
        if f['datasets'][0] not in dataset_name:
            if len(dataset_name) <= 1:
                dataset_name.append(str(f['datasets'][0]))

    def exist_list():
        exist_TNM_titles.append(TNM_file_title)
        exist_dwnld_url.append(TNM_file_URL)
        if product_is_zip:
            exist_zip_list.append(local_zip_path)
            extract_zip_list.append(local_zip_path)
        else:
            exist_tile_list.append(local_tile_path)

    # Assign needed parameters from returned JSON
    tile_API_count = int(return_JSON['total'])
    tiles_needed_count = 0
    size_diff_tolerance = 5
    exist_dwnld_size = 0
    if tile_API_count > 0:
        dwnld_size = []
        dwnld_url = []
        dataset_name = []
        TNM_file_titles = []
        exist_dwnld_url = []
        exist_TNM_titles = []
        exist_zip_list = []
        exist_tile_list = []
        extract_zip_list = []
        # for each file returned, assign variables to needed parameters
        for f in return_JSON['items']:
            TNM_file_title = f['title']
            TNM_file_URL = str(f['downloadURL'])
            TNM_file_size = int(f['sizeInBytes'])
            TNM_file_name = TNM_file_URL.split(product_url_split)[-1]
            local_file_path = os.path.join(work_dir, TNM_file_name)
            local_zip_path = os.path.join(work_dir, TNM_file_name)
            local_tile_path = os.path.join(work_dir, TNM_file_name)
            file_exists = os.path.exists(local_file_path)
            file_complete = None
            # if file exists, but is incomplete, remove file and redownload
            if file_exists:
                existing_local_file_size = os.path.getsize(local_file_path)
                # if local file is incomplete
                if abs(existing_local_file_size - TNM_file_size) > size_diff_tolerance:
                    # add file to cleanup list
                    cleanup_list.append(local_file_path)
                    # NLCD API query returns subsets that cannot be filtered before
                    # results are returned. gui_subset is used to filter results.
                    if not gui_subset:
                        tiles_needed_count += 1
                        down_list()
                    else:
                        if gui_subset in TNM_file_title:
                            tiles_needed_count += 1
                            down_list()
                        else:
                            continue
                else:
                    if not gui_subset:
                        tiles_needed_count += 1
                        exist_list()
                        exist_dwnld_size += TNM_file_size
                    else:
                        if gui_subset in TNM_file_title:
                            tiles_needed_count += 1
                            exist_list()
                            exist_dwnld_size += TNM_file_size
                        else:
                            continue
            else:
                if not gui_subset:
                    tiles_needed_count += 1
                    down_list()
                else:
                    if gui_subset in TNM_file_title:
                        tiles_needed_count += 1
                        down_list()
                        continue
        
    # return fatal error if API query returns no results for GUI input
    elif tile_API_count == 0:
        gscript.fatal("Zero tiles available for given input parameters.")

    # number of files to be downloaded 
    file_download_count = len(dwnld_url)

    # remove existing files from download lists
    for t in exist_TNM_titles:
        if t in TNM_file_titles:
            TNM_file_titles.remove(t)
    for url in exist_dwnld_url:
        if url in dwnld_url:
            dwnld_url.remove(url)
    
    # messages to user about status of files to be kept, removed, or downloaded
    if exist_zip_list:
        exist_msg = "\n{0} of {1} files/archive(s) exist locally and will be used by module.".format(len(exist_zip_list), tiles_needed_count)
        gscript.message(exist_msg)
    if exist_tile_list:
        exist_msg = "\n{0} of {1} files/archive(s) exist locally and will be used by module.".format(len(exist_tile_list), tiles_needed_count)
        gscript.message(exist_msg)
    if cleanup_list:
        cleanup_msg = "\n{0} existing incomplete file(s) detected and removed. Run module again.".format(len(cleanup_list))
        gscript.fatal(cleanup_msg)

    # formats JSON size from bites into needed units for combined file size
    if dwnld_size:
        total_size = sum(dwnld_size)
        len_total_size = len(str(total_size))
        if 6 < len_total_size < 10:
            total_size_float = total_size * 1e-6
            total_size_str = str("{0:.2f}".format(total_size_float) + " MB")
        if len_total_size >= 10:
            total_size_float = total_size * 1e-9
            total_size_str = str("{0:.2f}".format(total_size_float) + " GB")
    else:
        total_size_str = '0'
    
    # Prints 'none' if all tiles available locally
    if TNM_file_titles:
        TNM_file_titles_info = "\n".join(TNM_file_titles)
    else:
        TNM_file_titles_info = 'none'
    
    # Formatted return for 'i' flag
    if file_download_count <= 0:
        data_info = "\n\nUSGS file(s) to download: NONE"
    else:
        data_info = (
                     "USGS file(s) to download:",
                     "-------------------------",
                     "Total download size:\t{size}",
                     "Tile count:\t{count}",
                     "USGS SRS:\t{srs}",
                     "USGS tile titles:\n{tile}",
                     "-------------------------",
                     )
        data_info = '\n'.join(data_info).format(size=total_size_str,
                                                count=file_download_count,
                                                srs=product_srs,
                                                tile=TNM_file_titles_info)
    print data_info
    
    if gui_i_flag:
        gscript.info("To download USGS data, remove <i> flag, and rerun r.in.usgs.")
        sys.exit()
    
    # USGS data download process
    if file_download_count <= 0:
        gscript.message("Extracting existing USGS Data...")
    else:
        gscript.message("Downloading USGS Data...")

    TNM_count = len(dwnld_url)
    download_count = 0
    local_tile_path_list = []
    local_zip_path_list = []
    patch_names = []

    # Download files
    for url in dwnld_url:
        # create file name by splitting name from returned url
        file_name = url.split(product_url_split)[-1]
        # add file name to local download directory
        local_file_path = os.path.join(work_dir, file_name)
        try:
            # download files in chunks rather than write complete files to memory
            dwnld_req = urllib2.urlopen(url, timeout=12)
            download_bytes = int(dwnld_req.info()['Content-Length'])
            CHUNK = 16 * 1024
            with open(local_file_path, "wb+") as local_file:
                count = 0
                steps = int(download_bytes / CHUNK) + 1
                while True:
                    chunk = dwnld_req.read(CHUNK)
                    gscript.percent(count, steps, 10)
                    count += 1
                    if not chunk:
                        break
                    local_file.write(chunk)
            local_file.close()
            download_count += 1
            # determine if file is a zip archive or another format
            if product_is_zip:
                local_zip_path_list.append(local_file_path)
            else:
                local_tile_path_list.append(local_file_path)
            file_complete = "Download {0} of {1}: COMPLETE".format(
                    download_count, TNM_count)
            gscript.info(file_complete)
        except urllib2.URLError:
            gscript.fatal("USGS download request has timed out. Network or formatting error.")
        except StandardError:
            cleanup_list.append(local_file_path)
            if download_count:
                file_failed = "Download {0} of {1}: FAILED".format(
                            download_count, TNM_count)
                gscript.fatal(file_failed)

    # sets already downloaded zip files or tiles to be extracted or imported
    if exist_zip_list:
        for z in exist_zip_list:
            local_zip_path_list.append(z)
    if exist_tile_list:
        for t in exist_tile_list:
            local_tile_path_list.append(t)
    if product_is_zip:
        if file_download_count == 0:
            pass
        else:
            gscript.message("Extracting data...")
        # for each zip archive, extract needed file
        for z in local_zip_path_list:
            # Extract tiles from ZIP archives
            try:
                with zipfile.ZipFile(z, "r") as read_zip:
                    for f in read_zip.namelist():
                        if f.endswith(product_extension):
                            extracted_tile = os.path.join(work_dir, str(f))
                            if os.path.exists(extracted_tile):
                                os.remove(extracted_tile)
                                read_zip.extract(f, work_dir)
                            else:
                                read_zip.extract(f, work_dir)
                if os.path.exists(extracted_tile):
                    local_tile_path_list.append(extracted_tile)
                    cleanup_list.append(extracted_tile)
            except:
                cleanup_list.append(extracted_tile)
                gscript.fatal("Unable to locate or extract IMG file from ZIP archive.")
    
    # operations for extracted or complete files available locally
    for t in local_tile_path_list:
        # create variables for use in GRASS GIS import process
        LT_file_name = os.path.basename(t)
        LT_layer_name = os.path.splitext(LT_file_name)[0]
        patch_names.append(LT_layer_name)
        in_info = ("Importing and reprojecting {0}...").format(LT_file_name)
        gscript.info(in_info)
        # import to GRASS GIS
        try:
            gscript.run_command('r.import', input=t, output=LT_layer_name,
                                resolution='value', resolution_value=product_resolution,
                                extent="region", resample=product_interpolation)
            if not gui_k_flag:
                cleanup_list.append(t)
        except CalledModuleError:
            in_error = ("Unable to import '{0}'").format(LT_file_name)
            gscript.fatal(in_error)

    # if control variables match and multiple files need to be patched, 
    # check product resolution, run r.patch
    
    # Check that downloaded files match expected count
    completed_tiles_count = len(local_tile_path_list)
    if completed_tiles_count == tiles_needed_count:
        if completed_tiles_count > 1:
            try:
                gscript.use_temp_region()
                # set the resolution
                if product_resolution:
                    gscript.run_command('g.region', res=product_resolution, flags='a')
                gscript.run_command('r.patch', input=patch_names,
                                    output=gui_output_layer)
                gscript.del_temp_region()
                out_info = ("Patched composite layer '{0}' added").format(gui_output_layer)
                gscript.verbose(out_info)
                # Remove files if 'k' flag
                if not gui_k_flag:
                    gscript.run_command('g.remove', type='raster',
                                        name=patch_names, flags='f')
            except CalledModuleError:
                gscript.fatal("Unable to patch tiles.")
        elif completed_tiles_count == 1:
            gscript.run_command('g.rename', raster=(patch_names[0], gui_output_layer))
        temp_down_count = "\n{0} of {1} tile/s succesfully imported and patched.".format(completed_tiles_count,
                          tiles_needed_count)
        gscript.info(temp_down_count)
    else:
        gscript.fatal("Error downloading files. Please retry.")

    # Keep source files if 'k' flag active
    if gui_k_flag:
        src_msg = ("<k> flag selected: Source tiles remain in '{0}'").format(work_dir)
        gscript.info(src_msg)

    # set appropriate color table
    if gui_product == 'ned':
        gscript.run_command('r.colors', map=gui_output_layer, color='elevation')

def cleanup():
    # Remove files in cleanup_list
    for f in cleanup_list:
        if os.path.exists(f):
            gscript.try_remove(f)

if __name__ == "__main__":
    options, flags = gscript.parser()
    atexit.register(cleanup)
    sys.exit(main())
