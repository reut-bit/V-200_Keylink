TEX = gx12_dual_band_gemini_x_setup.tex
PDF = gx12_dual_band_gemini_x_setup.pdf
ENGINE = xelatex
FLAGS = -interaction=nonstopmode

.PHONY: all clean

all: $(PDF)

$(PDF): $(TEX) v200doc.sty
	$(ENGINE) $(FLAGS) $(TEX)
	$(ENGINE) $(FLAGS) $(TEX)

clean:
	rm -f *.aux *.log *.out *.toc *.fls *.fdb_latexmk *.synctex.gz
