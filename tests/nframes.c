
void depth(void) {
  return;
}

int f(int n) {
  if (n==1) {
    depth();
    return 1;
  }
  else {
    return n*f(n-1);
  }
}

int main(void) {
  return f(20);
}