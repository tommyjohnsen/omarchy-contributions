// MIT; new standalone contribution. Keep fill geometry independent of its width.
function finite(value) { return typeof value === "number" && isFinite(value) }

function widthFor(context) {
  var compact = finite(context.compact) ? Math.max(1, context.compact) : 36
  var margin = finite(context.margin) ? Math.max(0, context.margin) : 4
  if (context.vertical) return finite(context.barSize) ? Math.max(1, context.barSize) : compact

  var positioned = finite(context.surfaceWidth) && finite(context.ownStart)
  if (positioned) compact = Math.min(compact, Math.max(1, context.surfaceWidth-context.ownStart-margin))
  // The clock must be independently anchored from the left section. Supporting
  // same-row fill requires a public stretch-layout API, not a feedback probe.
  if (context.ownRegion !== "left" || context.workspaceRegion !== "left" ||
      ["center", "centerBegin", "centerEnd", "right"].indexOf(context.clockRegion) === -1 ||
      !positioned || !finite(context.workspaceEnd) || !finite(context.clockStart) ||
      context.ownStart < context.workspaceEnd || context.leftFollower) return compact

  var boundary = finite(context.independentStart) ? Math.min(context.clockStart,context.independentStart) : context.clockStart
  var room = Math.min(boundary, context.surfaceWidth)-context.ownStart-margin
  return Math.max(1, Math.floor(room))
}
