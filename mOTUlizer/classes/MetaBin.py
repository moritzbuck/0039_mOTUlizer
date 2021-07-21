from os.path import join as pjoin
import tempfile
import sys
from subprocess import Popen, PIPE, call
import os
import shutil
from mOTUlizer.config import FASTA_EXTS, MAX_COMPLETE
from mOTUlizer.errors import *


class MetaBin:
    def __repr__(self) :
        return "< bin {name} with {n} gene_clusterss>".format(n = len(self.gene_clustering) if self.gene_clustering else "NA", name = self.name)

    def __init__(self, name,nucleotide_file = None, amino_acid_file = None, gff_file = None, complet = 100, contamin = 0):
        self.name = name
        self.gene_clustering = None
        self.amino_acid_file = amino_acid_file
        self.amino_acids = None
        self.nucleotide_file = nucleotide_file
        self.contigs = None
        self.gff_file = gff_file
        self.gff = None
        self.original_complet = complet
        self.original_contamin = contamin
        if self.original_complet > MAX_COMPLETE:
            self.original_complet =  MAX_COMPLETE
        self.new_completness = None

        self.gff = GFF(self.gffs_files[g], self.fnas[g]) for g in self.genomes}

        self.faas = {}
        t_dir = tempfile.TemporaryDirectory()
        for genome,gff in self.gffs.items():
            self.faas[genome] = pjoin(t_dir.name, genome + ".faa")
            gff.make_fasta(self.faas[genome], "aas")

    def get_amino_acids(self):
        if not self.amino_acids:
            if not self.amino_acid_file:
                if not self.gff_file:
                    raise CantAminoAcidsError("You need either a gff or a amino-acid fasta if you want to use amino-acids")
                if not self.nucleotide_file:
                    raise CantAminoAcidsError("You need an nucleotide fasta if you want to use a gff to get amino-acids")
                self.amino_acids = { feat.get_id() : feat.get_amino_acids() for feat in self.get_gff() if feat.feature == "CDS"}
            else :
                self.amino_acids = {s.id : s.seq for s in SeqIO(self.amino_acid_file, "fasta")}
        return self.amino_acids

    def get_gff(self):
        if not self.gff_file:
            CantGFFError("can't parse a gff if there ain't one")
        self.gff = GFF(self, self.gff_file)

    def get_contigs(self):
        if not self.nucleotide_file:
            CantNucleotideError("can't parse a nucleotide if there ain't one")
        self.gff = GFF(self, self.gff_file)


    def get_data(self):
        return { 'name' : self.name,
                 'faa-file' : self.faas,
                 'fna-file' : self.fnas,
                 'original_complet' : self.original_complet,
                 'original_contamin' : self.original_contamin,
                 'new_completness' : self.new_completness,
        }


    def overlap(self, target):
        return self.gene_clustering.intersection(target.gene_clustering)

    def estimate_nb_gene_clusters(self):
        assert self.new_completness != None, "new_completness not computed, please do"
        return 100*len(self.gene_clustering)/self.new_completness

    @classmethod
    def get_anis(cls, bins, outfile = None, method = "fastANI", block_size = 500, threads=1):
        if method == "fastANI":
            if not shutil.which('fastANI'):
                print("You need fastANI if you do not provide a file with pairwise similarities, either install it or provide pairwise similarities (see doc...)", file = sys.stderr)
                sys.exit(-1)
            fastani_file = tempfile.NamedTemporaryFile().name if outfile is None else outfile

            mags = [b.fnas for b in bins]

            mag_blocks = [mags[i:(i+block_size)] for i in list(range(0,len(mags), block_size))]

            if len(mag_blocks) > 1:
                print("You have more then {bsize} bins, so we will run fastANI in blocks, if it crashes due to memory, make smaller blocks".format(bsize = block_size), file=sys.stderr)

            with open(fastani_file, "w") as handle:
                handle.writelines(["query\tsubject\tani\tsize_q\tsize_s\n"])

            for i,bloc1 in enumerate(mag_blocks):
                b1_tfile = tempfile.NamedTemporaryFile().name

                with open(b1_tfile, "w") as handle:
                    handle.writelines([l +"\n" for l in bloc1])

                for j,bloc2 in enumerate(mag_blocks):
                        print("doing bloc {i} and {j}".format(i = i, j=j), file = sys.stderr)
                        b2_tfile = tempfile.NamedTemporaryFile().name
                        with open(b2_tfile, "w") as handle:
                            handle.writelines([l  +"\n" for l in bloc2])

                        out_tfile = tempfile.NamedTemporaryFile().name
                        call("fastANI --ql {b1} --rl {b2} -o {out} -t {threads} 2> /dev/null".format(b1 = b1_tfile, b2 = b2_tfile, out = out_tfile, threads = threads), shell = True)
                        with open(out_tfile) as handle:
                            new_dat = ["\t".join([ll for ll in l.split()]) +"\n" for l in handle.readlines()]
                        with open(fastani_file, "a") as handle:
                            handle.writelines(new_dat)

                        os.remove(out_tfile)
                        os.remove(b2_tfile)

            os.remove(b1_tfile)
            with open(fastani_file) as handle:
                handle.readline()
                out_dists = {(os.path.basename(l.split()[0]), os.path.basename(l.strip().split()[1])) : float(l.split()[2]) for l in handle}
                out_dists = {( ".".join(k[0].split(".")[:-1]) if any([k[0].endswith(ext) for ext in FASTA_EXTS]) else k[0],
                               ".".join(k[1].split(".")[:-1]) if any([k[1].endswith(ext) for ext in FASTA_EXTS]) else k[1] ): v
                               for k,v in out_dists.items() }
#                tfile = lambda k : ".".join(k.split(".")[:-1]) if (k.endswith(".fna") or k.endswith(".fa") or k.endswith(".fasta") or k.endswith(".fna") or k.endswith(".ffn")) else k
#                out_dists = {(tfile(k[0]),tfile(k[1])) : v for k,v in out_dists.items()}
            if outfile is None:
                os.remove(fastani_file)
        else :
            print("No other method for ani computation implemented yet")
            sys.exit()

        return out_dists
