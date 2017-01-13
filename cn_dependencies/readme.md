# View CN dependencies

A script to compute CN package dependencies, and a HTML file to render them.

The enclosed ``show_cn_dependencies`` bash script should be run on a CN. It examines the various DataONE .deb packages and evaluates the dependencies
specified in each package. The output is as a GraphViz .gv file.

The .gv generated can be rendered using GraphViz or viewed using a web browser
by visiting ``/cn_dependencies.html`` on the CN.

## Installation

1. Download the script and ``chmod a+x`` it
2. Download the html file and put it in ``/var/www``
3. Generate the .gv file using something like:
     ```
     sudo -c bash `./show_cn_dependencies > /var/www/cn_dependencies.gv`
     ```
