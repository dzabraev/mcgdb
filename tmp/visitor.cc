#include <clang-c/Index.h>

#include <iostream>

CXChildVisitResult visitor(CXCursor cursor, CXCursor, CXClientData) {
  auto cursorName = clang_getCursorDisplayName(cursor);
  auto cursorNameStr = std::string(clang_getCString(cursorName));
  CXSourceRange range = clang_getCursorExtent(cursor);
  CXSourceLocation location_start = clang_getRangeStart(range);
  CXSourceLocation location_end = clang_getRangeEnd(range);

  CXFile file;
  unsigned line[2];
  unsigned column[2];
  clang_getFileLocation(location_start, &file, &line[0], &column[0], nullptr);
  clang_getFileLocation(location_end, &file, &line[1], &column[1], nullptr);

  auto fileName = clang_getFileName(file);

  std::cout << clang_getCString(cursorName) << " at "
            << "start=" << line[0] << ":" << column[0] << " "
            << "end=" << line[1] << ":" << column[1]
            << " in " << clang_getCString(fileName)
            << std::endl;

  clang_disposeString(fileName);
  clang_disposeString(cursorName);

  return CXChildVisit_Recurse;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    return 1;
  }

  // Create an index with excludeDeclsFromPCH = 1, displayDiagnostics = 0
  CXIndex index = clang_createIndex(1, 0);

  // Speed up parsing by skipping function bodies
  CXTranslationUnit translationUnit = clang_parseTranslationUnit(
      index,
      argv[1],
      argv+2,
      argc-2,
      NULL,
      0,
      //CXTranslationUnit_None|CXTranslationUnit_KeepGoing
      CXTranslationUnit_SingleFileParse
      );

  // Visit all the nodes in the AST
  CXCursor cursor = clang_getTranslationUnitCursor(translationUnit);
  clang_visitChildren(cursor, visitor, 0);

  // Release memory
  clang_disposeTranslationUnit(translationUnit);
  clang_disposeIndex(index);

  return 0;
}
