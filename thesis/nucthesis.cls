%% Noroff university College Thesis Style file - adapted from Barry Iwrins implementation in 2021
%% Inspired by   RU Computer Science Class  2010
%% (c) Barry Irwin 2021

%% CHANGELOG - see CHANGLE log file
%% August 2021 - initial revision
%% September 2022 - additions to citations and cleanups
%% September 2024 - Notable adustments, switch to APA
%% October 2025 - minor tweaks ot layout and reference processing.
%% TODO
%    Fine-tuning margins to deal with two sided printing (potentially) - fix is use twoside vs oneside
%    Citation templates /guides are provided in the proposal.



%---------------------------------------------------------------------------------
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{nucthesis}[2026/08/20 Noroff University College Thesis Class]

\def\currversion{August 20, 2026} 

\newcommand{\Degree}{Bachelor of Interpretive Dance} %% default

%% Stop fonts being too small.
\DeclareOption{10pt}{
  \ClassWarningNoLine{CSE}{
    The `10pt' option is not allowed in the `nucthesis' class}
  \OptionNotUsed
}
\DeclareOption{12pt}{
  \ClassWarningNoLine{CSE}{
    The `12pt' option is not allowed in the `nucthesis' class}
  \OptionNotUsed
}
\DeclareOption{14pt}{
  \ClassWarningNoLine{CSE}{
    The `14pt' option is not allowed in the `nucthesis' class}
  \OptionNotUsed
}

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{report}}
\ProcessOptions\relax
%\ProcessOptions
% we are based off the core report class so pass this through  *again*
%
\if@twoside%
    \LoadClass[11pt, a4paper, twoside, openright]{report} %% twoside=true
\else%
    \LoadClass[11pt, a4paper, oneside]{report} %% twoside=false
\fi%

% Ensure URL is loaded first
\PassOptionsToPackage{hyphens}{url} % make sure to split on hyphens for urls
\RequirePackage[hyphens]{url} % make sure to split on hyphens for urls
\RequirePackage{hyperref} % There are lots of options that can be added here. RTFM - https://ctan.org/pkg/hyperref?lang=en
\RequirePackage{doi} % hyperlinks DOI's in refs

%% character encoding
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}

\RequirePackage{graphicx}
%page Setup - DO NOT ALTER
%\RequirePackage{geometry}
%    \if@twoside% twoside=true
%        \geometry{left=25mm,right=25mm,bindingoffset=10mm, top=20mm,bottom=35mm} %% 
%    \else% twoside=false
%        \geometry{left=25mm,right=25mm,bindingoffset=0mm, top=20mm,bottom=35mm} %% 
%    \fi%
\RequirePackage{eso-pic} % needed for front cover
% \usepackage{transparent}
%% packages dealing with layout
\RequirePackage[a4paper]{geometry}
\RequirePackage[dvipsnames]{xcolor} 
\RequirePackage{fancybox}
\RequirePackage{fancyhdr} %%Fancy headings
\RequirePackage{verbatim}
\RequirePackage[parfill]{parskip} %Sets full justification and paragraph spacing} 
\RequirePackage{xstring}
\RequirePackage{enumitem} % allow compressed lists.

%% Tables related
\RequirePackage{longtable} %%For tables, that exceed one page
\RequirePackage{booktabs}

%layout control
\RequirePackage{float}
\RequirePackage{wrapfig}
\RequirePackage{caption}
\RequirePackage{subcaption}

% \RequirePackage{lipsum}
\RequirePackage{quotchap} % makes pretty chapters
%% some other useful components
\RequirePackage{calc}
\RequirePackage{ifthen}
\RequirePackage{setspace}
%\RequirePackage{acmart} %% required for ACM CCS - see https://www.acm.org/publications/class-2012

\RequirePackage[english]{babel} % set UK spelling.
\RequirePackage[autostyle]{csquotes}
\MakeOuterQuote{"}
\MakeInnerQuote{´} %prevents backwards quote symbols

%duplication?
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{report}}
\ProcessOptions\relax

%% define font
\RequirePackage{helvet}
\renewcommand{\familydefault}{\sfdefault}

%%% refereces
\RequirePackage[style=apa,backend=biber]{biblatex}
\DeclareLanguageMapping{british}{british-apa}
\addbibresource{ref.bib}


%% define Hyperref  details here
\hypersetup{
	colorlinks=true, %set true if you want coloured links
	linktoc=all,     %set to all if you want both sections and subsections linked
	linkcolor=black,  %choose some colour if you want links to stand out	
	citecolor=black,
%	citecolor=blue,
    filecolor=blue,      
    urlcolor=blue, % URLs via \url and \hyperref
}



 
\newcommand{\NUCLogo}{images/nuc.png}


\newcommand\frontmatter{%
    \cleardoublepage
  %\@mainmatterfalse
  \pagenumbering{roman}}

\newcommand\mainmatter{%
    \cleardoublepage
 % \@mainmattertrue
  \pagenumbering{arabic}}

\newcommand\backmatter{%
  \if@openright
    \cleardoublepage
  \else
    \clearpage
  \fi
 % \@mainmatterfalse
   }


%disabled till we have alternate types
\newcommand{\DegType}{partial fulfilment}
%\newcommand{\degree}[1]{\renewcommand{\Degree}{#1}}
%\newcommand{\partdegree}[1]{\renewcommand{\Degree}{#1} \renewcommand{\DegType}{partial fulfilment}}
%\newcommand{\fulldegree}[1]{\renewcommand{\Degree}{#1} \renewcommand{\DegType}{partial fulfilment}}
\newcommand{\TitleBox}{false}
\newcommand{\titlebox}[1]{\renewcommand{\TitleBox}{#1}}
\newcommand{\Logo}{true}
% default is on - to disable in tex \renewcommand{\Logo}{false}
\newcommand{\logo}[1]{\renewcommand{\Logo}{#1}}

\newcommand{\SetMargins}[3]{
	\setlength{\hoffset}{-25mm + (#1 / 2)}
	\setlength{\voffset}{-25mm}
	\setlength{\oddsidemargin}{#1}
	\setlength{\evensidemargin}{#1}
	\setlength{\topmargin}{#1 / 2}
	\ifthenelse{\boolean{#2}}{\setlength{\headheight}{15pt}% header material
		\setlength{\headsep}{20pt}}{\setlength{\headheight}{0pt}%
		\setlength{\headsep}{0pt}}
	\ifthenelse{\boolean{#3}}{\setlength{\footskip}{35pt}}% footer material
		{\setlength{\footskip}{0pt}}
	\setlength{\textheight}{\paperheight - \footskip - \headsep - \headheight - \topmargin - #1}
	\setlength{\textwidth}{\paperwidth - (#1 * 2) } %  - (#1 / 3)}
    \addtolength\oddsidemargin{-0.5cm}
    \addtolength\evensidemargin{-1cm}
    \textwidth=\dimexpr\textwidth-1cm\relax
	\setlength\parskip{\bigskipamount}
	\setlength\parindent{0pt}
	\onehalfspacing
}

\SetMargins{2.2cm}{true}{true} %2.5cm margin, enable head and foot skips
%\linespread{1.5} %% 1.5 spacing for document body (dealt with above) 

%rename Bibliography to references when using bibtex
\renewcommand\bibname{References}
% set some full details
\newcommand\ackname{Acknowledgements}

\newcommand{\keywords}[1]{\vspace{1cm}\newline\textbf{Keywords:} \textit{#1}}

% replaced with deparate declaration
% \newcommand{\plagdeclaration}{
%     \chapter*{Declaration}
%     I declare that the work presented for assessment in this submission is my own, that it has not previously been presented for another assessment, and that work completed by others has been appropriately acknowledged.
%     \vspace{1.5cm} \newline
%     \textbf{Name}: \myname{} \hspace{2cm} \textbf{Date}: \today 
%     \thispagestyle{empty} 
% }
% \newcommand{\plagdeclarationblank}{
%     \chapter*{Declaration}
%     I declare that the work presented for assessment in this submission is my own, that it has not previously been presented for another assessment, and that work completed by others has been appropriately acknowledged.
%     \vspace{3cm} \newline
%     \textbf{Name}: \noindent\rule{5.5cm}{0.4pt}  \hspace{1.5cm} \textbf{Date}: \noindent\rule{4cm}{0.4pt} 
%     \thispagestyle{empty} 
% } 

\renewcommand{\headrulewidth}{\iffloatpage{0pt}{0.4pt}}

\pagestyle{fancy}
\lhead{\sectionmark}
\rhead{}
\cfoot{\thepage}
\renewcommand{\chaptermark}[1]{\markboth{\MakeUppercase{\chaptername}\ \thechapter}{}}


%\fancypagestyle{plain}{\fancyhf{}\fancyhead[R]{\thepage}}
\fancyhf{}\fancyhead[R]{\thepage}
\fancyhead[L]{\iffloatpage{}{\slshape \rightmark}}

% \newcommand{\mylocation}{Kristiansand, Norway}

%% 2024 new skinning of paper format
\parindent 0mm
% \setlength{\oddsidemargin}{0mm}
% \setlength{\evensidemargin}{0mm}
% \setlength{\topmargin}{-20mm}
% \setlength{\textwidth}{165mm}
% \setlength{\textheight}{260mm}
% \newcommand\BackgroundPic{%
%     \put(40,-70){%
%         \parbox[b][\paperheight]{\paperwidth}{%
%             \vfill
%             \centering
%              \IfStrEq{\degree}{ADS}{
%                 \includegraphics[width=1.28\textwidth]{images/FrontCover - Bachelor in Applied Data Science2024.pdf}
%             }{
%                 \IfStrEq{\degree}{CSE}{
%                     \includegraphics[width=1.0\paperwidth]{images/FrontCover - Bachelor in Cyber Security2024.pdf}
%                 }{
%                     \IfStrEq{\degree}{DFO}{
%                     \includegraphics[width=1.28\textwidth]{images/FrontCover - Bachelor in Digital Forensics2024.pdf}
%                     }
%                 }
%                 }
%             % \includegraphics[width=\paperwidth,height=\paperheight,%
%             % keepaspectratio]{images/FrontCover - Bachelor in Cyber Security3.pdf}%
%             \vfill
% }}}
\newcommand\BackgroundPic{%
    \put(40,-85){%
        \parbox[b][\paperheight]{\paperwidth}{%
            \vfill
            \centering
             \IfStrEq{\degree}{ADS}{
                \includegraphics[width=1.38\textwidth]{images/FrontCover - Bachelor in Applied Data Science2025.pdf}
            }{
                \IfStrEq{\degree}{CSE}{
                    \includegraphics[width=1.01\paperwidth]{images/FrontCover - Bachelor in Cyber Security2025.pdf}
                }{
                    \IfStrEq{\degree}{DFO}{
                    \includegraphics[width=1.38\textwidth]{images/FrontCover - Bachelor in Digital Forensics2025.pdf}
                    }
                }
                }
            % \includegraphics[width=\paperwidth,height=\paperheight,%
            % keepaspectratio]{images/FrontCover - Bachelor in Cyber Security3.pdf}%
            \vfill
}}}


% \renewcommand{\maketitle}{%
% 	\begin{titlepage}%
% 	\begin{center}%
% 	\ifthenelse{\boolean{\Logo}}{\includegraphics[scale=0.4]{\NUCLogo}\vfill}{\vspace*{\fill}}%
% 	\ifthenelse{\boolean{\TitleBox}}{
% 	\Ovalbox{\begin{minipage}[c][\height + 6cm][c]{(\textwidth * 3) / 4}\begin{center}%
% 	\vspace*{\fill}\LARGE\textsc{\@title}%
% 	\large\vfill%
% 	Submitted in \DegType\\%
% 	of the requirements of the degree of\vskip 0.5em\textsc{\Degree}\vskip 0.5em%
% 	of Noroff University College%
% 	\vfill\Large\@author\vspace*{\fill}%
% 	\end{center}\end{minipage}}}{%

% 	\begin{center}%
% 	\vspace*{\fill}\LARGE\textsc{\@title}%
% 	\large\vfill%
% 	Submitted in \DegType\\%
% 	of the requirements of the degree of\vskip 0.5em\textsc{\Degree}\vskip 0.5em%
% 	of Noroff University College%
% 	\vfill\Large\@author\vspace*{\fill}%
% 	\end{center}}%

% 	\vfill\normalsize%
% 	\emph{\mylocation}\\%
% 	\ifcase\month\or  January\or February\or March\or April\or May\or June\or July\or August\or September\or October\or November\or December\fi
%   \space\number\year
% 	\month \year  %@date
%   \end{center}%
% 	\end{titlepage}%
% }


% \if@titlepage
%   \newenvironment{ack}{%
%       \titlepage
%       \null\vfil
%       \@beginparpenalty\@lowpenalty
%       \begin{center}%
%         \bfseries \ackname
%         \@endparpenalty\@M
%       \end{center}}%
%      {\par\vfil\null\endtitlepage}
% \else
%   \newenvironment{ack}{%
%       \if@twocolumn
%         \section*{\ackname}%
%       \else
%         \small
%         \begin{center}%
%           {\bfseries \ackname\vspace{-.5em}\vspace{\z@}}%
%         \end{center}%
%         \quotation
%       \fi}
%       {\if@twocolumn\else\endquotation\fi}
% \fi

% \newcommand\acmname{ACM Computing Classification System Classification}

% \if@titlepage
%   \newenvironment{acm}{%
%       \titlepage
%       \null\vfil
%       \@beginparpenalty\@lowpenalty
%       \begin{center}%
%         \bfseries \acmname
%         \@endparpenalty\@M
%       \end{center}}%
%      {\par\vfil\null\endtitlepage}
% \else
%   \newenvironment{acm}{%
%       \if@twocolumn
%         \section*{\acmname}%
%       \else
%         \small
%         \begin{center}%
%           {\bfseries \ackname\vspace{-.5em}\vspace{\z@}}%
%         \end{center}%
%         \quotation
%       \fi}
%       {\if@twocolumn\else\endquotation\fi}
% \fi
%% Providing Section guidence
\newcommand{\guidebox}[1]{%
    \colorbox{gray!20}{%
    \begin{minipage}{0.99\textwidth}
    \small{\textbf{\textsc{NUC Bachelor Project Guidance}}:\newline}
    \noindent\rule{\textwidth}{0.4pt}
    \singlespacing %reduce spacing
    \small{#1}%{\textit{#1}}
    \end{minipage}%
    }%
    \newline
}


\newcommand{\guideabs}{\guidebox{Your Abstract should succinctly sum up your work in 200-300 words. The abstract should briefly explain the problem or topic being investigated, the aim of the project, the approach or methods used, the main findings or expected contribution, and the overall significance of the work. It should be understandable without requiring the reader to consult the main thesis. Avoid including citations, detailed background information, or information that is not covered in the thesis. \\  \\Choose 3-5 keywords to include in the \textbf{Keywords} section below. Choose terms that someone might use when searching for research similar to yours. This must \textbf{not} exceed one page.}
\newline}


\newcommand{\guideack}{\guidebox{Your Acknowledgements are generally free form in structure. You should acknowledge anyone who has assisted you with the project. Any funders of the research or your studies are typically mentioned here as well, where applicable. This section must \textbf{not} exceed one page.}}


\newcommand{\guideintro}{\guidebox{The Introduction sets the scene, contextualises your research, and provides an overview of the project. This chapter contains some commonly used sections. At a minimum, you should define and populate the following:
    \begin{enumerate}[nosep]
        \item Problem Statement
        \item Research Objectives
        \item Scope and Limitations
%\section{Document Conventions} %enable if you have specific formatting styles you want to tell the reader about
        \item Document Structure
    \end{enumerate}
    This chapter establishes and justifies your research. Explain why the problem is worth investigating, and clearly define the scope and limitations of your work.\newpage}}
    
\newcommand{\guidelit}
{\guidebox{The \textbf{Literature Review} has two primary goals:
\begin{enumerate}[nosep]
        \item \textbf{A review of related literature and research}
        Examining what other researchers have investigated in the field. This provides academic foundation for your work. It shows what you are building and basing your work on (contextualisation) and it gives you something to compare your results to in later chapters.
        \item \textbf{Technology review and primer}
        An exploration of appropriate technologies that you will be using in your investigation. This is also where you need to explain any particularly technical concepts that readers may not be familiar with.
\end{enumerate}
The majority of your references should appear in your Literature Review chapter. Any major work(s) you rely on later \textbf{must} be introduced here. The chapter should not simply summarise sources; it should critically compare them, identify relevant themes or disagreements, and establish how your research relates to the existing body of knowledge.
}}
% Your introduction should clearly explain the overall research topic and the depth of the information to be presented; it often also explains the types of sources that will be used. If your literature review is part of a larger research proposal or project, its introduction can be combined with the introduction of your paper. The body of your literature review is intended to give your audience an overview of the already-available research on your topic. 

% You must also conclude the key findings! The conclusion of your literature review can be used to explain your intended research question. If your literature review has revealed a gap in general understanding, your conclusion can explain the significance of that gap. 
% Remember to end your chapter with a summary of the key points, and a link to how they relate to the chapters following.

\newcommand{\guideanalysis}{\guidebox{\textbf{Analysis}-based projects should clearly document the process of data collection, processing, and analysis. 
\begin{itemize}
    \item Where did you collect data?
    \item How did you collect it?
    \item How did you store and process your data?
    \item What techniques were used to produce the results?
\end{itemize}
An analysis is about how results were produced.  The interpretation and broader implications of these results should be dealt with in the following chapter.}}

\newcommand{\guideimplementation}{\guidebox{\textbf{Implementation}-driven projects usually aim at the production of an `artefact' - such as  code, software, a dataset, or a physical object such as a game. This chapter should discuss both the design process followed (why did you make it like this?) and the resulting implementation approach (how did you build it?). Any design/implementation trade-offs and decisions made should be discussed.}}

\newcommand{\guidemethod}{\guidebox{\textbf{The Methodology chapter} describes and justifies the methods and techniques employed in the research process. This could be the approach you took, who or what you collected data from, how you collected it and how you analysed it. Provide detail around the tools and procedures used for collecting data e.g surveys, interviews, observations, experiments, etc. Explain how data was actually collected, including the timeline when appropriate and describe the methods used to analyse the collected data. Where applicable, specify any qualitative analysis techniques. Explain measures taken to ensure the reliability and validity of the research. Mention any methodological limitations and their potential impact on your findings. Conclude by summarising the methodology, emphasising its strengths and justifying the choices made.}}

\newcommand{\guideresults}{\guidebox{The Results chapter presents the findings of your investigation. These can take many different forms based on how the project was conducted. The key here is to critically evaluate your results. Compare and contrast your findings with the existing body of literature introduced in the Literature Review. The interpretation of the results and their broader implications should be discussed here. This will provide final links in the golden thread of the planned work, the implementation and the findings.}}

\newcommand{\guideconclusion}{\guidebox{The Conclusion brings the thesis to a close by drawing together the research, findings, and overall argument. It should not introduce new information, evidence, or facts relating to the research. Typically, this chapter should be structured as follows:
    \begin{enumerate}
        \item {\textbf{Introduction}}
        Briefly introduce the purpose of the conclusion and draw together the preceding chapters.
        \item {\textbf{Summary of Research}}
        Briefly summarises the work conducted 2-3 sentences per chapter is sufficient.
        \item {\textbf{Research Objectives}}
                For each research objective established in the Introduction, evaluate the extent to which it has been achieved. Refer back to the relevant sections of the thesis that support these evaluations and provide a link back to the section(s) which justify this).
        \item {\textbf{Research Contribution}}
        Summarise the contribution made by your research, clearly define any outputs, findings,  or artefacts produced.
        \item {\textbf{Future Work}}
        You built your work on the `shoulders of giants'. How could someone continue to build on your work? Choose 3-4 areas of further exploration and/or expansion of your work.
    \end{enumerate}
}}

\newcommand{\Rtext}[1]{\color[HTML]{F03F24}{#1}\color[HTML]{000000}}
%% code for handling word counts
\newcommand{\detailtexcount}[1]{%
  \immediate\write18{texcount -merge -sum -q #1.tex output.bbl > #1.wcdetail }%
  \verbatiminput{#1.wcdetail}%
}

\newcommand{\quickwordcount}[1]{%
  \immediate\write18{texcount -1 -sum -merge -q #1.tex output.bbl > #1-words.sum }%
  \input{#1-words.sum} words%
}

\newcommand{\quickwordcountnoref}[1]{%
  \immediate\write18{texcount -1 -sum -merge -q #1.tex  > #1-words.sum }%
  \input{#1-words.sum} words%
}

\newcommand{\noroffcount}[1]{%
  \immediate\write18{texcount -v0 -q -total  -sum -merge -q #1.tex > #1-words.noroff }%
  \input{#1-words.noroff} %
}
%
%Words with Refs:\quickwordcount{main}
%
%Words Without refs: \quickwordcountnoref{main}

\newcommand{\NUCwordcount}[1]{
    \chapter*{Word Count Metrics}
    \framebox{%
    \begin{minipage}{0.95\textwidth}
    \textbf{NUC Bachelor Project Word Count}:\\
    \noroffcount{#1}
    NOTE: References are excluded.
    \end{minipage}}
}

%%% ---------------------------- END OF CLASS ----------------------------