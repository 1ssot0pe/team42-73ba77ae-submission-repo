/**
 * SpecimenField (design.md 6.1). No props.
 * A fixed layer behind the whole app with three blurred colour fields, so the liquid glass has
 * something to refract. Render it once, at the root. Styles live in src/styles/base.css.
 */
export function SpecimenField() {
  return (
    <div className="specimen-field" aria-hidden="true">
      <span className="v" />
      <span className="e" />
      <span className="p" />
    </div>
  );
}
