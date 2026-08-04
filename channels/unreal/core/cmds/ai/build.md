- How to build;
	- Full build; ".build TARGET VARIANT"
	- Individual module; ".build TARGET VARIANT <modulename>", where "modulename" can be derived by looking up the tree for "<modulename>.Build.cs"
	  a file.
	- Single .cpp file; ".build TARGET VARIANT <cpppath>"
    - TARGET and VARIANT are mandatory (never empty)
    - Never quote TARGET
    - Defaults; TARGET=editor, VARIANT=development
