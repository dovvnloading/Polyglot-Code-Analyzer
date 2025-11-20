# Polyglot Code Analyzer



**[The Website](https://dovvnloading.github.io/Polyglot-Code-Analyzer/)**

---

![License](https://img.shields.io/github/license/dovvnloading/Polyglot-Code-Analyzer?style=for-the-badge&color=005ca0)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Framework](https://img.shields.io/badge/GUI-PySide6-41cd52?style=for-the-badge&logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=for-the-badge)

Polyglot Code Analyzer is a sophisticated, desktop-based static analysis tool designed to provide comprehensive insights into software projects of varying complexity. Built upon the Qt framework (PySide6), it features a custom-engineered Neumorphic user interface that prioritizes visual clarity and ergonomic interaction.

This tool goes beyond simple line counting; it parses directory structures to distinguish between executable code, comments, and whitespace across dozens of programming languages. Additionally, it identifies technical debt by scanning for standard marker tags, offering developers an immediate high-level overview of project health.

## User Interface

The application features a fully responsive Neumorphic design system with seamless Light and Dark mode toggling.

<table>
  <tr>
    <th width="50%">Light Mode</th>
    <th width="50%">Dark Mode</th>
  </tr>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/b28929ce-8a7e-4123-a906-3a1cb2e8f73d" alt="Polyglot Analyzer Light Mode" width="100%"></td>
    <td><img src="https://github.com/user-attachments/assets/c85bdc24-196e-499c-b5bd-a8333b432c5e" alt="Polyglot Analyzer Dark Mode" width="100%"></td>
  </tr>
</table>


---
---

## Download Polyglot Code Analyzer

### ↓ Direct Download (v1.0.0)
[Download Polyglot.exe](https://github.com/dovvnloading/Polyglot-Code-Analyzer/releases/download/v1.0.0/Polyglot.exe)


---
---

## Features

*   **Multi-Language Support**: Native recognition for over 50 file extensions, covering backend, frontend, systems programming, and scripting languages.
*   **Granular Metrics**:
    *   **Code**: Executable lines of code.
    *   **Comments**: Documentation and inline comments (supports `#`, `//`, `--`, `%`, `<!--`).
    *   **Blanks**: Whitespace analysis to determine code density.
*   **Technical Debt Scanning**: Automated detection of `TODO`, `FIXME`, `HACK`, `BUG`, and `XXX` tags to highlight areas requiring attention.
*   **Visual Composition**: Generates proportional bar charts to visualize the ratio of code to comments.
*   **Neumorphic GUI**: A custom implementation of Soft UI design principles using advanced Qt painting techniques, featuring bi-directional shadowing and floating elements.
*   **Threaded Analysis**: Non-blocking background workers ensure the UI remains responsive during the scanning of large repositories.

## Installation

### Prerequisites

*   Python 3.10 or higher
*   pip (Python Package Manager)

### Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/dovvnloading/Polyglot-Code-Analyzer.git
    cd Polyglot-Code-Analyzer
    ```

2.  Install the required dependencies:
    ```bash
    pip install PySide6
    ```

3.  Run the application:
    ```bash
    python main.py
    ```

## Usage

1.  Launch the application.
2.  Click the **SELECT PROJECT** button.
3.  Navigate to the root directory of the software project you wish to analyze.
4.  The application will scan the directory tree. Progress is indicated by the bar at the top.
5.  Upon completion, a detailed report is rendered, showing file counts, line breakdowns, and language composition.

## Supported Languages

The analyzer supports a wide array of file types, including but not limited to:

*   **Systems**: C, C++, Rust, Go, Assembly (`.asm`, `.s`)
*   **Web**: HTML, CSS, JavaScript (`.js`, `.jsx`), TypeScript (`.ts`, `.tsx`), PHP
*   **Data**: JSON, XML, YAML, SQL
*   **Scripting**: Python, Ruby, Perl, Lua, Shell (`.sh`, `.bash`, `.ps1`)
*   **Mobile/App**: Swift, Kotlin, Java, Dart, C#

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.


Copyright [2025] [Matthew R. Wesney]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
