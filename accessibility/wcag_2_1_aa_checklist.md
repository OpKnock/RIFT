# WCAG 2.1 AA Compliance Checklist for RIFT Clinical Dashboard
# Phase 19: Product UX - Accessibility compliance for clinical use

## Perceivable

### 1.1 Non-text Content (A)
- [ ] All images have alt text describing clinical relevance
- [ ] Charts/graphs have text alternatives (data tables)
- [ ] SVG gauges have aria-label with current value
- [ ] Icon buttons have accessible names

### 1.2 Time-based Media (A)
- [ ] No auto-playing audio/video
- [ ] Captions for any instructional videos
- [ ] Audio descriptions for clinical workflow demos

### 1.3 Adaptable (AA)
- [ ] Semantic HTML structure (header, main, nav, section)
- [ ] Heading hierarchy (h1→h2→h3) for clinical data
- [ ] Table headers for metric grids (scope="col/row")
- [ ] Form labels associated with inputs (for/id)

### 1.4 Distinguishable (AA)
- [ ] Color contrast ≥ 4.5:1 for text (clinical values)
- [ ] Color contrast ≥ 3:1 for UI components (gauges, borders)
- [ ] No color-only information (use icons + text for status)
- [ ] Text resize up to 200% without horizontal scroll
- [ ] Focus indicators visible (3px solid outline)

## Operable

### 2.1 Keyboard Accessible (A)
- [ ] All interactive elements reachable via Tab
- [ ] Logical tab order (clinical workflow sequence)
- [ ] No keyboard traps in modal dialogs
- [ ] Skip to main content link

### 2.2 Enough Time (A)
- [ ] No auto-advancing carousels on clinical data
- [ ] Session timeout warning with extend option
- [ ] Real-time updates pausable (WebSocket streams)

### 2.3 Seizures and Physical Reactions (A)
- [ ] No flashing > 3Hz (gauge animations < 2Hz)
- [ ] Reduced motion preference respected

### 2.4 Navigable (AA)
- [ ] Page titles describe clinical context
- [ ] Focus order matches visual layout
- [ ] Section headings for each clinical panel
- [ ] Breadcrumbs for multi-step workflows

## Understandable

### 3.1 Readable (A)
- [ ] Page language declared (lang="en")
- [ ] Medical abbreviations expanded on first use
- [ ] Plain language for patient-facing copy

### 3.2 Predictable (AA)
- [ ] Consistent navigation across clinical views
- [ ] Form submission doesn't auto-navigate
- [ ] Error messages identify field + suggestion

### 3.3 Input Assistance (AA)
- [ ] Required fields marked (aria-required)
- [ ] Error messages linked to fields (aria-describedby)
- [ ] Input format hints (placeholder/pattern)

## Robust

### 4.1 Compatible (A)
- [ ] Valid HTML5 (W3C validator)
- [ ] ARIA roles used correctly (role="alert" for critical)
- [ ] Custom elements have proper semantics
- [ ] Status messages announced (aria-live regions)

## Clinical-Specific Requirements

### Critical Values Display
- [ ] Red/amber/green status has text labels
- [ ] Numeric values always shown with units
- [ ] Trend arrows have alt text ("rising", "falling")
- [ ] Guardian action badges have tooltips

### Real-time Updates
- [ ] Live region for risk score changes (aria-live="polite")
- [ ] Critical alerts use aria-live="assertive"
- [ ] WebSocket reconnection status announced

### Data Export
- [ ] CSV/JSON exports have headers
- [ ] PDF evidence bundles tagged for screen readers
- [ ] Provenance data accessible

## Testing Checklist

### Automated (CI)
- [ ] axe-core: 0 violations (AA)
- [ ] pa11y: 0 errors (WCAG 2.1 AA)
- [ ] Lighthouse CI: Accessibility score ≥ 95

### Manual
- [ ] Screen reader (NVDA/JAWS) full workflow
- [ ] Keyboard-only navigation all clinical panels
- [ ] Zoom 200% no horizontal scroll
- [ ] High contrast mode (Windows/OSX)
- [ ] Voice control (Dragon/Talos)

## RIFT Dashboard Specific

### Pages to Audit
1. `/` - Twin overview (gauges, trajectories, evidence)
2. `/twin/demo` - Demo patient workflow
3. `/evidence` - Evidence bundles
4. `/admin` - Experiment management

### Components to Verify
- Risk gauge (SVG + aria)
- Trajectory chart (canvas + data table)
- Evidence table (sortable, paginated)
- Guardian panel (color + text status)
- Prospective lock form (validation)

## Resources
- [WCAG 2.1 AA Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [axe-core Rules](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md)
- [pa11y Documentation](https://pa11y.org/)
- [Lighthouse CI Accessibility](https://github.com/GoogleChrome/lighthouse-ci)