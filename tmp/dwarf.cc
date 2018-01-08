#include <err.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

#include <libdwarf.h>
#include <dwarf.h>
#include <libelf.h>

#include <list>
#include <iostream>
#include <unordered_map>
#include <unordered_set>
#include <string>
#include <regex>
#include <fstream>

#include <boost/filesystem.hpp>

namespace fs = boost::filesystem;

class LazyFile {
  public :
    fs::path filename;
    LazyFile (fs::path filename) {
      this->filename = filename;
      exhausted = false;
      file = std::fstream(filename.string(), std::fstream::in);
    }

    const std::string & operator[] (int line_number) {
      static std::string empty_string = "";
      if (read_before (line_number))
        return lines[line_number];
      else
        return empty_string;
    }

  private :
    bool exhausted;
    std::vector<std::string> lines;
    int n_lines_read {0};
    std::fstream file;
    std::regex regex_line_directive {"\\s*#\\s*line"};

    bool ignore_line (std::string & line) {
      std::smatch match;
      if(std::regex_search(line, match, regex_line_directive)) //ignore this directives #line 1 "test"
        return true;
      return false;
    }

    bool read_before(int line_num) {
      if (line_num<n_lines_read)
        return true;
      if (exhausted)
        return false;
      std::string line;
      while (std::getline(file, line)) {
        if (ignore_line (line))
          continue;
        lines.push_back(line);
        n_lines_read++;
        if (line_num<n_lines_read)
          return true;
      }
      exhausted = true;
      return false;
    }
};

class CompilationUnit {
  public:
    CompilationUnit (fs::path filename) {
      this->filename = filename;
    };
    ~CompilationUnit (void) {
    };
    friend std::ostream &operator<<(std::ostream&, const CompilationUnit&);

    bool add_include(std::string fullname, std::string incl_path) {
      return includes.insert({fullname, incl_path}).second;
    }

    fs::path filename;
    std::unordered_map<std::string,std::string> includes;
};

std::ostream &
operator<<(std::ostream& stream, const CompilationUnit& cu) {
  stream<<"COMPILATION UNIT: "<<cu.filename<<std::endl;
  for (auto && [ key, value ]: cu.includes) {
    stream<<"  "<<value<<" --> "<<key<<std::endl;
  }
  return stream;
}


class ObjectFile {
  public:

    ObjectFile (const char *filename) {
      int fd;
      void *data;
      struct stat sb;
      if ((fd = open(filename, O_RDONLY)) < 0 ||
        fstat(fd, &sb) < 0 ||
        (data = mmap(NULL, sb.st_size, PROT_READ, MAP_PRIVATE, fd, (off_t) 0)) == MAP_FAILED)
      {
        /*error*/
        abort();
      }
      init (data, sb.st_size);
    }

    ObjectFile (void *data, size_t n) {
      init (data, n);
    }

    ~ObjectFile (void) {
      Dwarf_Error err;
      dwarf_finish (this->dbg, &err);
      elf_end (this->elf);
      for (auto item : headers_files) {
        delete item.second;
      }
    }

    void debug_print(void) {
      for (auto it : compilation_units) {
        std::cout << it.second << "\n";
      }
    }

  private:
    void init (void *data, size_t n) {
      init_dwarf (data, n);
      extract_compilation_units ();
    }

    void init_dwarf (void *data, size_t n) {
      Dwarf_Error err;
      int res;

      elf_version(EV_CURRENT);
      if ((this->elf = elf_memory((char *) data, n)) == NULL) {
        /*error*/
        printf("elf_memory(): %s\n", elf_errmsg (elf_errno()));
        if (elf_version(EV_CURRENT) == EV_NONE)
          errx(EXIT_FAILURE, "ELF library too old");
        abort();
      }
      res = dwarf_elf_init (this->elf, DW_DLC_READ, NULL, NULL, &this->dbg, &err);
      if (res != DW_DLV_OK) {
        /*error*/
        printf ("dwarf_init: %s", dwarf_errmsg (err));
        assert (res==DW_DLV_OK);
      }
    }

    void extract_compilation_units(void) {
      int res;
      Dwarf_Error err;

      while (true) {
        Dwarf_Die cu_die = 0;

        Dwarf_Unsigned cu_header_length = 0;
        Dwarf_Unsigned abbrev_offset = 0;
        Dwarf_Half     address_size = 0;
        Dwarf_Half     version_stamp = 0;
        Dwarf_Half     offset_size = 0;
        Dwarf_Half     extension_size = 0;
        Dwarf_Sig8     signature;
        Dwarf_Unsigned typeoffset = 0;
        Dwarf_Unsigned next_cu_header = 0;
        Dwarf_Half     header_cu_type = DW_UT_compile;
        Dwarf_Bool     is_info = true;

        res = dwarf_next_cu_header_d(dbg,is_info,&cu_header_length,
            &version_stamp, &abbrev_offset,
            &address_size, &offset_size,
            &extension_size,&signature,
            &typeoffset, &next_cu_header,
            &header_cu_type,&err);


        if(res == DW_DLV_ERROR) {
            printf("Error in dwarf_next_cu_header: %s\n", dwarf_errmsg(err));
            exit(1);
        }
        if(res == DW_DLV_NO_ENTRY) {
            /* Done. */
            break;
        }

        res = dwarf_siblingof_b (dbg, NULL,is_info, &cu_die, &err);
        if (res != DW_DLV_OK) {
          printf ("siblingof cu header %s\n", dwarf_errmsg (err));
          break;
        }



        Dwarf_Attribute comp_name_attr = 0;
        char *comp_name_attr_str=0;
        res = dwarf_attr(cu_die, DW_AT_name, &comp_name_attr, &err);
        if (res != DW_DLV_OK) {
          printf ("dwarf_attr: %s\n", dwarf_errmsg (err));
          continue;
        }
        res = dwarf_formstring(comp_name_attr, &comp_name_attr_str, &err);
        if (res!=DW_DLV_OK)
          continue;

        Dwarf_Attribute comp_dir_attr = 0;
        char *comp_dir_attr_str=0;
        res = dwarf_attr(cu_die, DW_AT_comp_dir, &comp_dir_attr, &err);
        if (res != DW_DLV_OK) {
          printf ("dwarf_attr: %s\n", dwarf_errmsg (err));
          continue;
        }
        res = dwarf_formstring(comp_dir_attr, &comp_dir_attr_str, &err);
        if (res!=DW_DLV_OK)
          continue;

        char **srcfiles;
        Dwarf_Signed srcfilescount;
        dwarf_srcfiles (cu_die, &srcfiles, &srcfilescount, &err);

        fs::path comp_unit_path = fs::weakly_canonical (fs::path (comp_dir_attr_str) / fs::path (comp_name_attr_str));
        CompilationUnit cu(comp_unit_path);
        populate_cu (cu, cu_die);
        compilation_units.insert ({comp_unit_path.string(), cu});

        dwarf_dealloc(dbg, cu_die, DW_DLA_DIE);
      }
    }

    void
    populate_cu_macro (CompilationUnit & cu, Dwarf_Macro_Context mcontext, Dwarf_Unsigned number_of_ops) {
      int res;
      Dwarf_Error err = 0;
      std::stack<fs::path> header_stack;

      for (Dwarf_Unsigned k = 0; k < number_of_ops; ++k) {
        Dwarf_Unsigned  section_offset = 0;
        Dwarf_Half      macro_operator = 0;
        Dwarf_Half      forms_count = 0;
        const Dwarf_Small *formcode_array = 0;
        Dwarf_Unsigned  line_number = 0;
        Dwarf_Unsigned  index = 0;
        Dwarf_Unsigned  offset =0;
        const char    * macro_string =0;

        res = dwarf_get_macro_op(mcontext,
            k, &section_offset,&macro_operator,
            &forms_count, &formcode_array,&err);
        if (res != DW_DLV_OK) {
            printf ("ERROR from  dwarf_get_macro_op(): %s",
                dwarf_errmsg (err));
            return;
        }

        switch(macro_operator) {
          case DW_MACRO_start_file: {
            res = dwarf_get_macro_startend_file(mcontext,
              k,&line_number,
              &index,
              &macro_string,&err);
            if (res != DW_DLV_OK) {
              printf ("ERROR from dwarf_get_macro_startend_file(): %s",
                  dwarf_errmsg (err));
              return;
            }
            if (macro_string) {
              fs::path include_filename = fs::weakly_canonical (fs::path (macro_string));
              std::string sp = include_filename.string();
              if (line_number>0) {
                fs::path parent_filename = header_stack.top();
                std::string header_string = get_header_string (parent_filename.string(), line_number-1);
                if (!header_string.empty())
                  cu.add_include(sp, header_string);
              }
              header_stack.push (include_filename);
              if (headers_files.find (sp)==headers_files.end ()) {
                headers_files[sp] = new LazyFile (include_filename);
              }
            }
            break;
          }
          case DW_MACRO_end_file: {
            header_stack.pop();
            break;
          }
          case DW_MACRO_import: {
            res = dwarf_get_macro_import(mcontext,
                k,&offset,&err);
            if (res != DW_DLV_OK) {
              printf ("ERROR from dwarf_get_macro_import(): %s",
                  dwarf_errmsg (err));
              return;
            }
            break;
          }
        }
      }
    }

    std::string get_header_string (std::string include_filename, int line_number) {
      LazyFile *f=headers_files[include_filename];
      std::smatch include_match;
      if(std::regex_search(f[0][line_number], include_match, include_regex)) {
        return include_match[1];
      }
      return std::string("");
    }

    void populate_cu (CompilationUnit & cu, Dwarf_Die cu_die) {
      Dwarf_Unsigned version = 0;
      Dwarf_Macro_Context mcontext = 0;
      Dwarf_Unsigned macro_unit_offset = 0;
      Dwarf_Unsigned number_of_ops = 0;
      Dwarf_Unsigned ops_total_byte_len = 0;
      Dwarf_Error err;
      int res;


      res = dwarf_get_macro_context (cu_die,
         &version,
         &mcontext,
         &macro_unit_offset,
         &number_of_ops,
         &ops_total_byte_len,
         &err);

      if (res==DW_DLV_OK) {
        populate_cu_macro (cu, mcontext, number_of_ops);
        dwarf_dealloc_macro_context(mcontext);
      }
      else {
        if (err)
          printf ("dwarf_get_macro_context: %s\n", dwarf_errmsg (err));
        return;
      }
    }

    std::regex include_regex {"\\s*#include\\s*[<\"]([^\">]+)[>\"]"};
    Dwarf_Debug dbg;
    Elf *elf;
    std::unordered_map<std::string, CompilationUnit> compilation_units;
    std::unordered_map<std::string,LazyFile *> headers_files;
};






int main (int argc, char **argv) {
  if (argc<2)
    errx (EXIT_FAILURE, "argc<2");

  const char *fname = argv[1];

  ObjectFile obj(fname);
  obj.debug_print();

  return 0;
}
