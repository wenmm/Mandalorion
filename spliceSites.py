#!/usr/bin/env python3
# Christopher Vollmers
# Roger Volden

import sys
import argparse


parser = argparse.ArgumentParser()

parser.add_argument('--infile', '-i', type=str, action='store')
parser.add_argument('--path', '-p', type=str, action='store')
parser.add_argument('--cutoff', '-c', type=float, action='store')
parser.add_argument('--genome_file', '-g', type=str, action='store')
parser.add_argument('--refine', '-r', type=str, action='store')
parser.add_argument('--sam_file', '-s', type=str, action='store')
parser.add_argument('--splice_site_width', '-w', type=int, action='store')
parser.add_argument('--minimum_read_count', '-m', type=int, action='store')
parser.add_argument('--white_list_polyA', '-W', type=str, action='store')


if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(0)
args = parser.parse_args()
infile = args.infile
out_path = args.path + '/'  # path where you want your output files to go
cutoff = args.cutoff
genome_file = args.genome_file
refine = args.refine
sam_file = args.sam_file
splice_site_width = args.splice_site_width
minimum_read_count = args.minimum_read_count
white_list_polyA=args.white_list_polyA

out = open(out_path + '/SS.bed', 'w')


def scan_for_best_bin(entry, dist_range, density_dict, peak_areas, chrom, side):
    best_extra_list, peak_center = 0, 0
    cov_area = {}
    best_dirs = {'+': 0, '-': 0}
    for x in dist_range:
        extra_list_exp = 0
        dirs = {'+': 0, '-': 0}
        cov_set = {}
        called = False
        for y in dist_range:
            if entry + x + y in peak_areas[chrom][side]:
                called = True
        if called:
            continue
        for y in dist_range:
            if entry + x + y in density_dict:
                for item in density_dict[entry + x + y]:
                    extra_list_exp += 1
                    dirs[item[4]] += 1
                    for covered_position in item[3]:
                        if covered_position not in cov_set:
                            cov_set[covered_position] = 0
                        cov_set[covered_position] += 1

        if extra_list_exp > best_extra_list:
            best_extra_list = extra_list_exp
            peak_center = entry + x
            cov_area = cov_set
            best_dirs = dirs

    return best_extra_list, peak_center, cov_area, best_dirs


def determine_cov(cov_area, chrom, reverse, peak_center, histo_cov):
    cov = [0]
    cov_area2 = []
    for covered_position, count in cov_area.items():
        if count > 1:
            cov_area2.append(covered_position)

    cov_area = sorted(cov_area2, reverse=reverse)
    counter = 0
    for base_f in cov_area:
        count = False
        if reverse and base_f < peak_center:
            count = True
        elif not reverse and base_f > peak_center:
            count = True
        if count:
            if counter <= 3:
                counter += 1
                base_f = myround(base_f)
                if base_f in histo_cov[chrom]:
                    cov.append(histo_cov[chrom][base_f])
            else:
                break
    cov = max(cov)
    return cov, cov_area


def myround(x, base=10):
    '''Rounds to the nearest base'''
    return int(base * round(float(x) / base))


def find_peaks(density_dict, out, peaks, reverse, cutoff, histo_cov, side, peak_areas, chrom):
    if reverse:
        dist_range = range(splice_site_width, -splice_site_width, -1)
    else:
        dist_range = range(-splice_site_width, splice_site_width)

    entry_list = []
    for entry in density_dict:
        entry_list.append([entry, density_dict[entry]])
    for entry, density in sorted(entry_list, key=lambda x: len(x[1]), reverse=True):

        if len(density) < minimum_read_count:
            break
        if entry in peak_areas[chrom][side]:
            continue
        best_extra_list, peak_center, cov_area, best_dirs = scan_for_best_bin(entry, dist_range, density_dict, peak_areas, chrom, side)

        cov, cov_area = determine_cov(cov_area, chrom, reverse, peak_center, histo_cov)

        if cov > 0:
            proportion = round(best_extra_list / cov, 3)
            if proportion > cutoff:
                Left_to_Right = best_dirs['+']
                Right_to_Left = best_dirs['-']
                Type = ''

                if Left_to_Right < Right_to_Left:
                    Type = '3' if reverse else '5'

                elif Left_to_Right > Right_to_Left:
                    Type = '5' if reverse else '3'

                if not Type:
                    continue
                peaks += 1
                out.write(chrom + '\t' + str(peak_center - splice_site_width)
                          + '\t' + str(peak_center + splice_site_width) + '\t'
                          + str(Type) + side + str(peaks) + '_'
                          + str(peak_center - splice_site_width) + '_'
                          + str(peak_center + splice_site_width) + '_'
                          + str(proportion) + '\t' + str(peaks) + '\n')
                for base in range(peak_center - splice_site_width, peak_center + splice_site_width + 1):
                    peak_areas[chrom][side][base] = 1

    return peaks, peak_areas


def collect_reads(reads, sam_file, dir_dict, target_chrom):
    histo_left_bases, histo_right_bases, histo_cov = {}, {}, {}
    histo_cov[target_chrom] = {}
    histo_left_bases[target_chrom] = {}
    histo_right_bases[target_chrom] = {}

    for line in reads:
        a = line.strip().split('\t')
        chrom = a[13]
        name = a[9].split('_')[0]
        dirn = a[8]
        if name in dir_dict:
            dirn = dir_dict[name]

        length = int(a[10])
        begin, span = int(a[15]), int(a[16])
        blocksizes = a[18].split(',')[:-1]
        blockstarts = a[20].split(',')[:-1]
        cov_set = set()
        low_bounds, up_bounds = [], []
        aligned_bases = 0
        for x in range(0, len(blocksizes)):
            blockstart = int(blockstarts[x])
            blocksize = int(blocksizes[x])
            aligned_bases += blocksize
            blockend = blockstart + blocksize
            for y in range(0, blocksize, 10):
                rounded = myround(blockstart + y)
                cov_set.add(rounded)
            for yy in range(y, blocksize):
                rounded = myround(blockstart + yy)
                cov_set.add(rounded)
            if blockstart != begin:
                up_bounds.append(blockstart)
            if blockend != span:
                low_bounds.append(blockend)

        for rounded in cov_set:
            if rounded not in histo_cov[chrom]:
                histo_cov[chrom][rounded] = 0
            histo_cov[chrom][rounded] += 1

        if aligned_bases / length <= 0.70:
            continue
        for low_bound in low_bounds:
            if low_bound not in histo_left_bases[chrom]:
                histo_left_bases[chrom][low_bound] = []
            histo_left_bases[chrom][low_bound].append([0, begin, span, cov_set, dirn])
        for up_bound in up_bounds:
            if up_bound not in histo_right_bases[chrom]:
                histo_right_bases[chrom][up_bound] = []
            histo_right_bases[chrom][up_bound].append([0, begin, span, cov_set, dirn])

    return histo_left_bases, histo_right_bases, histo_cov


def parse_genome(input_file, left_bounds, right_bounds):
    polyAWhiteList=[]
    chrom_list = set()
    gene_dict = {}
    for line in open(input_file):
        a = line.strip().split('\t')
        if len(a) <= 7:
            continue
        if a[2] == 'exon':
            testKey = a[8].split('transcript_id "')[1].split('"')[0]
            if not gene_dict.get(testKey):
                gene_dict[testKey] = []
            gene_dict[testKey].append((a[0], a[3], a[4], a[6]))

    for transcript_id in gene_dict:
        transcript_data = gene_dict[transcript_id]

        chrom = transcript_data[0][0]
        direction=transcript_data[0][3]
        chrom_list.add(chrom)
        if chrom not in right_bounds:
            left_bounds[chrom] = {'5': [], '3': []}
            right_bounds[chrom] = {'5': [], '3': []}

        start = sorted(transcript_data, key=lambda x: int(x[1]))[0][1]
        end = sorted(transcript_data, key=lambda x: int(x[2]), reverse=True)[0][2]
        direction=transcript_data[0][3]

        if direction=='+':
            polyAWhiteList.append((chrom,direction,end,transcript_id))
        elif direction=='-':
            polyAWhiteList.append((chrom,direction,start,transcript_id))

        for entry in transcript_data:
            if entry[1] != start:
                if entry[3] == '+':
                    right_bounds[chrom]['3'].append(int(entry[1]) - 1)
                elif entry[3] == '-':
                    right_bounds[chrom]['5'].append(int(entry[1]) - 1)
            if entry[2] != end:
                if entry[3] == '+':
                    left_bounds[chrom]['5'].append(int(entry[2]))
                if entry[3] == '-':
                    left_bounds[chrom]['3'].append(int(entry[2]))
    return chrom_list, left_bounds, right_bounds, polyAWhiteList


def make_genome_bins(bounds, side, peaks, chrom, peak_areas):
    for type1 in ['5', '3']:
        covered = {}
        position_list = sorted(bounds[type1], key=int)
        for index1 in range(0, len(position_list)):
            if index1 in covered:
                continue
            sub_list = [position_list[index1]]
            for index2 in range(index1, len(position_list)):
                if position_list[index2] - max(sub_list) <= splice_site_width:
                    sub_list.append(position_list[index2])
                    covered[index2] = 1
                else:
                    break
            single = False
            if len(sub_list) > 1:
                splice_dists = []
                for splice_pos in range(0, len(sub_list) - 1):
                    splice_dists.append(int(sub_list[splice_pos + 1]) - int(sub_list[splice_pos]))
                if min(splice_dists) > 3:
                    for x in range(0, len(sub_list), 1):
                        if x != 0:
                            start = int(sub_list[x] - ((sub_list[x] - sub_list[x - 1]) / 2))
                        else:
                            start = int(sub_list[x]) - 1
                        if x != len(sub_list) - 1:
                            end = int(sub_list[x] + ((sub_list[x + 1] - sub_list[x]) / 2))
                        else:
                            end = int(sub_list[x]) + 1

                        out.write(chrom + '\t' + str(start) + '\t' + str(end)
                                  + '\t' + type1 + side + str(peaks) + '_'
                                  + str(start) + '_' + str(end) + '_A' + '\t'
                                  + str(peaks) + '\n')
                        for base in range(start, end + 1):
                            peak_areas[chrom][side][base] = 1
                        peaks += 1
                else:
                    single = True
            else:
                single = True
            if single:
                start = min(sub_list) - splice_site_width
                end = max(sub_list) + splice_site_width
                out.write(chrom + '\t' + str(start) + '\t' + str(end) + '\t'
                          + type1 + side + str(peaks) + '_' + str(start) + '_'
                          + str(end) + '_A' + '\t' + str(peaks) + '\n')
                for base in range(start, end + 1):
                    peak_areas[chrom][side][base] = 1
                peaks += 1

    return peaks, peak_areas


def get_alignment_dir(sam_file):
    dir_dict = {}
    dir_conversion = {
        ('0', '+'): '+',
        ('0', '-'): '-',
        ('16', '+'): '-',
        ('16', '-'): '+',
    }

    for line in open(sam_file):
        if line[0] == '@':
            continue
        a = line.strip().split('\t')
        read_name = a[0].split('_')[0]
        read_dir = a[1]
        if read_dir in ['0', '16']:
            dirn = [x.split('ts:A:')[1] for x in a[10:] if 'ts:A:' in a]
            if dirn:
                dir_dict[read_name] = dir_conversion[(read_dir, dirn[0])]
    return dir_dict


def collect_chroms(isoform_psl, chroms):
    for line in open(isoform_psl):
        a = line.strip().split('\t')
        chrom = a[13]
        chroms.add(chrom)
    return chroms

def split_reads(infile,chrom_list):
    readDict={}
    for chrom in chrom_list:
        readDict[chrom]=[]
    for line in open(infile):
        a=line.strip().split('\t')
        chrom=a[13]
        if chrom not in readDict:
            readDict[chrom]=[]
        readDict[chrom].append(line)
        chrom_list.add(chrom)
    return readDict, chrom_list

def main():
    left_bounds, right_bounds = {}, {}
    if genome_file!='None':
        print('\tparsing annotated splice sites')
        chrom_list, left_bounds, right_bounds, polyAWhiteList = parse_genome(genome_file, left_bounds, right_bounds)
    else:
        print('\tNo genome annotation provided, so splice sites will be entirely read derived and no polyA sites will be white-listed')
        chrom_list=set()
        polyAWhiteList=[]

    outPolyA=open(out_path+'/polyAWhiteList.bed','w')
    if white_list_polyA=='1':
        print(len(polyAWhiteList), 'poly(A) sites whitelisted')
        for chrom,direction,end,transcript_id in polyAWhiteList:
            polyA=int(end)
            polyAstart=polyA-20
            polyAend=polyA+20
            outPolyA.write('%s\t%s\t%s\t%s\t%s\t%s\n' %(chrom,str(polyAstart),str(polyAend),transcript_id,'0',direction))
    outPolyA.close()

    Left_Peaks = 0
    Right_Peaks = 0
    dir_dict = get_alignment_dir(sam_file)
    print('\tloading reads')
    readDict, chrom_list = split_reads(infile, chrom_list)

    peak_areas = {}
    print(sorted(list(chrom_list)))
    for chrom in sorted(list(chrom_list)):
        print('\tnow processing ', chrom)
        print('\t\tparsing reads')
        histo_left_bases, histo_right_bases, histo_cov = collect_reads(readDict[chrom], sam_file, dir_dict, chrom)

        peak_areas[chrom] = {}
        peak_areas[chrom]['l'] = {}
        peak_areas[chrom]['r'] = {}
        if chrom not in left_bounds:
            left_bounds[chrom] = {'5': [], '3': []}
        if chrom not in right_bounds:
            right_bounds[chrom] = {'5': [], '3': []}
        if 'g' in refine:
            Left_Peaks_old = Left_Peaks
            Right_Peaks_old = Right_Peaks
            Left_Peaks, peak_areas = make_genome_bins(left_bounds[chrom], 'l', Left_Peaks, chrom, peak_areas)
            Right_Peaks, peak_areas = make_genome_bins(right_bounds[chrom], 'r', Right_Peaks, chrom, peak_areas)

            print(
                '\t\tparsed annotation-based splice-sites',
                Left_Peaks - Left_Peaks_old,
                Right_Peaks - Right_Peaks_old,
            )
        Left_Peaks_old = Left_Peaks
        Right_Peaks_old = Right_Peaks
        Left_Peaks, peak_areas = find_peaks(histo_left_bases[chrom], out, Left_Peaks, True, cutoff, histo_cov, 'l', peak_areas, chrom)
        Right_Peaks, peak_areas = find_peaks(histo_right_bases[chrom], out, Right_Peaks, False, cutoff, histo_cov, 'r', peak_areas, chrom)

        print(
            '\t\tdetected read-based splice-sites',
            Left_Peaks - Left_Peaks_old,
            Right_Peaks - Right_Peaks_old,
        )


main()
