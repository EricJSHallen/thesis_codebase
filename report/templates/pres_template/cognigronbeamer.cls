% Beamer-based classfile for presentations for the Rijksuniversiteit Groningen

% author: Philipp Klein

% updated and modified by Sebastian Hallén

% Inspired by rug15beamer by Siep Kroonenberg (C) 2015.
% version 1.4 (2015/10/15)

% For internal use at the Rijksuniversiteit Groningen.

% version 1 (2020/12/09) (comment Sebastian uncertain of original notation yyyy/[(mm/dd) or (dd/mm)]
% version 2 (10/04/2026) %dd/mm/yyyy -> updated image structure, should work on VScode now.
% Removed unneeded test structures and options.
% Not fitting to any template offered by the RUG

% See Beamer manual section 16.3 for more about templates

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{cognigronbeamer}[2026/10/04 v2]

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% option processing

\newif\if@english\@englishfalse
\DeclareOption{english}{\@englishtrue}
\DeclareOption{dutch}{\@englishfalse}

\newcommand\@sizeopt{10pt}
\DeclareOption{10pt}{\renewcommand\@sizeopt{10pt}}
\DeclareOption{11pt}{\renewcommand\@sizeopt{11pt}}
\DeclareOption{12pt}{\renewcommand\@sizeopt{12pt}}
\DeclareOption{14pt}{\renewcommand\@sizeopt{14pt}}

%%% new options

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{beamer}}
\ExecuteOptions{dutch,10pt}
\ProcessOptions\relax

\LoadClass[\@sizeopt]{beamer}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% colors
\definecolor{RuGred}{RGB}{204,0,0}
\definecolor{RuGwhite}{gray}{1.0}
\setbeamercolor*{normal text}{fg=black,bg=white}
\setbeamercolor*{structure}{fg=black}
\setbeamercolor*{alerted text}{fg=RuGred}
\setbeamercolor*{title}{fg=black}


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% defining user data
\let\@facname\@empty
\def\facname#1{%
  \def\@facname{\lowercase{#1}}}

\let\@group\@empty
\def\group#1{%
  \def\@group{\lowercase{#1}}}
  
\let\@inst\@empty
\def\inst#1{%
  \def\@inst{\lowercase{#1}}}

\let\@extralogo\@empty
\def\extralogo#1{%
  \def\@extralogo{#1}}

% slide header images
\def\templatedir{../templates/pres_template}
\def\@titleleftimage{\templatedir/header.png}
\def\@titlerightimage{\templatedir/webheader.png}
\def\@stdrightimage{\templatedir/logo.png}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% fonts; depends on engine and available fonts and packages

\newif\if@fontspec \@fontspecfalse
\ifxetex \@fontspectrue \fi
\ifluatex \@fontspectrue \fi

\newcommand\guilrug{\guilsinglright}

\if@fontspec
  \usefonttheme{professionalfonts}
  \RequirePackage{fontspec}
  \RequirePackage{unicode-math}
  \setsansfont[Ligatures=TeX]{helvet}
  \setmathfont{Cambria Math}
  \newfontface{\logofont}{Georgia}
\else
    % utopia: test for tfm, not for package which is psnfss
    \batchmode
    \font\X=putr7t
    \errorstopmode
    \ifx\X\nullfont
      \typeout{%
        ^^JLogo font Utopia not found! Using Computer Modern instead^^J}
      % encoding OT1 (is preloaded): avoid cmsuper or bitmapped EC fonts
      \def\logofont {\fontfamily\rmdefault\upshape\mdseries}
      \def\logofont {\fontfamily{cmr}\fontencoding{OT1}\upshape\mdseries}
      \renewcommand\guilrug{\ensuremath{>}}
    \else
      \RequirePackage[TS1,T1]{fontenc}
      \def\logofont {\fontfamily{put}\upshape\mdseries}
    \fi
    % arev: tfms and latex support installed together
    % so test for package.
    \IfFileExists{arev.sty}{%
      \RequirePackage[TS1,T1]{fontenc}
      \usefonttheme{professionalfonts}
      \RequirePackage{arevtext}
      % the full arev package doesn't work right without mathdesign
      \IfFileExists{mathdesign.sty}{\RequirePackage{arevmath}}{}
      \IfFileExists{beramono.sty}{%
        \renewcommand{\ttdefault}{fvm}
      }{% core package ae: virtual ec with cm, avoiding ec bitmaps
        \renewcommand{\ttdefault}{aett}
      }
    }{% no arev
      \typeout{%
         ^^JArev font package not found! Using cmss instead^^J}
      \AtBeginDocument{\sffamily\selectfont}
    }
\fi

\IfFileExists{microtype.sty}{%
  \RequirePackage[protrusion=true,expansion=false]{microtype}
}{}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% page layout

% because beamer has no knowledge of the slide backgrounds,
% we add struts to headline and navigation box to keep content from overrunning
% background header and extra logo, if applicable;
\newdimen\@clearance
\@clearance=0bp

\newdimen \realmargin
\realmargin=20bp
\geometry{papersize={480bp,270bp},%
hmargin=\realmargin,%
vmargin=0cm,%
head=0cm,% might be changed later
headsep=0pt,%
foot=0.0cm
}

\setbeamersize{text margin left=\realmargin}

% disable navigation symbols
\setbeamertemplate{navigation symbols}{}%

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% lists

\leftmargini=10bp
\def\@listi{%
  \leftmargin\leftmargini
  \labelwidth \leftmargin
  \labelsep 0bp
  \parsep 0bp
  \topsep 0bp
  \itemsep 3bp}
\let\@listI\@listi
\def\@listii{%
  \leftmargin\leftmargini
  \labelwidth \leftmargin
  \labelsep 0bp
  \parsep 0bp
  \topsep 3bp
  \itemsep 3bp}
\let\@listiii\@listii

\newcommand\bulletangle{{%
  \@tempdima=\f@size pt
  \advance\@tempdima-0.2\@tempdima
  \fontsize{\@tempdima}{\f@baselineskip}%
    \raisebox{.08\@tempdima}{\textbf{\texttt{>}}}}}

% hack to force from the outside left-alignment of the label;
% only for itemize
\setbeamertemplate{itemize item}%
  {\rlap{\guilrug}\rule{\labelwidth}{0bp}}
\setbeamertemplate{itemize subitem}%
  {\rlap{\scriptsize\textbullet}\rule{\labelwidth}{0bp}}
\setbeamertemplate{itemize subsubitem}%{--}
  {\rlap{--}\rule{\labelwidth}{0bp}}

% redefinition from beamerbaselocalstructure.sty
% note that beamer loads enumerate.sty
% and that \leftmargin and \labelwidth are redefined below

\def\beamer@enum@{%
  \beamer@computepref\@itemdepth% sets \beameritemnestingprefix
  \usebeamerfont{itemize/enumerate \beameritemnestingprefix body}%
  \usebeamercolor[fg]{itemize/enumerate \beameritemnestingprefix body}%
  \usebeamertemplate{itemize/enumerate \beameritemnestingprefix body begin}%
  \expandafter
    \list
      {\usebeamertemplate{\beamer@enumtempl}}
      {\leftmargin=15bp \labelwidth=\leftmargin
        \usecounter\@enumctr%
        \def\makelabel##1{\rlap{%
          \usebeamerfont*{enumerate \beameritemnestingprefix item}%
          \usebeamercolor[fg]{enumerate \beameritemnestingprefix
            item}##1}\hspace*{\leftmargin}}}%
  \beamer@cramped%
  \raggedright%
  \beamer@firstlineitemizeunskip%
}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% slide- and title backgrounds

% because beamer has no knowledge of the slide backgrounds,
% we add struts to headline and navigation box to keep content from overrunning
% background header and extra logo, if applicable;

\setbeamertemplate{headline}{%
  \hbox{\rule[-\@clearance]{0bp}{\@clearance}%
  \usebeamerfont{section in head/foot}\phantom{()}%
    \begin{beamercolorbox}[wd=.1\paperwidth,ht=0ex,dp=0.5ex]%
      {section in head/foot}%
      \usebeamerfont{section in head/foot}\phantom{()}%
    \end{beamercolorbox}%
  \null}
  \vskip0pt%
}

% date and frame number as part of the background, not of infolines
\beamer@noframenumberingfalse

% aim for fixed positions of `|' and of end of frame number
\def\@mydatepage{\llap{\insertdate~~}|%
  \hspace{3em}\llap{\insertframenumber}}

% background (logos, redline) for titleslide
\newcommand\titleback{%
  \unitlength=1bp
  \color{RuGred}%
  \begin{picture}(480,270)
    \put(0,240){\includegraphics[width=270bp,height=42bp,keepaspectratio]{\@titleleftimage}}
    \put(275,235){\includegraphics[width=205bp,height=75bp,keepaspectratio]{\@titlerightimage}}
    \let\barwidth \paperwidth
    \put(0,225.8){\rule{\barwidth}{10.2bp}}
  \end{picture}
}

% background (logos, redline) for all other slides
\newcommand\stdback{%
  \unitlength=1bp
  \color{RuGred}%
  \begin{picture}(480,270)
    \put(360,235){\includegraphics[width=120bp,height=42bp,keepaspectratio]{\@stdrightimage}}
    \let\barwidth \paperwidth
    \put(0,225.8){\rule{\barwidth}{10.2bp}}
    \put(431,229){\textcolor{RuGwhite}{\fontsize{4.5bp}{4.5bp}\selectfont\@mydatepage}}
  \end{picture}
}

\setbeamertemplate{background canvas}{\stdback}

\setbeamertemplate{frametitle}{%
  \leavevmode
  \LARGE\insertframetitle\par
}

\setbeamertemplate{title page}{%
  %\resizebox{\paperwidth}{\paperheight}{\@titleback}
  \vskip1cm
  \begin{beamercolorbox}{title}
    \LARGE \inserttitle\par
    \ifx\insertsubtitle\@empty \else
      \rule{0bp}{20bp}\footnotesize\insertsubtitle\par
    \fi
  \end{beamercolorbox}
  \vfill
  \ifx\@author \@empty \else
    \begin{beamercolorbox}{author}
      {\footnotesize\insertauthor}
    \end{beamercolorbox}
    \vskip6bp
  \fi
  \ifx\@institute\@empty \else
    \begin{beamercolorbox}{institute}
      {\footnotesize\insertinstitute}
    \end{beamercolorbox}
    \vskip3bp
  \fi
  \begin{beamercolorbox}{date}
    \footnotesize\insertdate%\rule[-4bp]{0bp}{4bp}
  \end{beamercolorbox}%
  \vfill
}

% Definition of what to do at \section and \section*
\AtBeginSection[%
\begin{frame}<beamer>% Do Section Title for \section*
    \frametitle{}%
    \begin{center}%
        \hspace{-\realmargin}\huge\insertsection%
    \end{center}%
\end{frame}%
]%
{%
\begin{frame}<beamer>% Do Section Title for \section
    \frametitle{}%
    \begin{center}%
        \hspace{-\realmargin}\huge\insertsection%
    \end{center}%
\end{frame}%
}%