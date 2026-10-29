/** The logo as a thin outline, then the name. Used small: bottom right of the home, top left of the other pages. */
export function Brand() {
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo-line.svg" alt="" width={24} height={24} />
      Caseback
    </>
  );
}
