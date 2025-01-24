function startAnimation(
  color,
  svg,
  y,
  x,
  containerWidth,
  effectiveHeight,
  keyframedFrames
) {
  let frameIndex = 0;
  let animationTimer;
  let controls;

  const frameDuration = TOTAL_DURATION / keyframedFrames.length;

  function updateVisualization(index) {
    const transition = svg
      .transition()
      .duration(frameDuration / currentSpeed)
      .ease(d3.easeCubicInOut); // Changed from easeLinear for smoother motion

    svg
      .select(".date-label")
      .transition(transition)
      .text(d3.timeFormat("%Y-%m-%d")(keyframedFrames[index].date));

    const reversedData = [...keyframedFrames[index].locationsData].reverse();
    return updateBars(
      color,
      reversedData,
      svg,
      x,
      y,
      containerWidth,
      transition
    );
  }

  function animate() {
    if (!isPlaying || frameIndex >= keyframedFrames.length) {
      if (frameIndex >= keyframedFrames.length) {
        frameIndex = 0;
        controls.updateProgress(frameIndex);
      }
      return;
    }

    updateVisualization(frameIndex).then(() => {
      controls.updateProgress(frameIndex);
      frameIndex++;
      animationTimer = setTimeout(animate, frameDuration / currentSpeed);
    });
  }

  function handleRestart() {
    if (animationTimer) {
      clearTimeout(animationTimer);
    }
    frameIndex = 0;
    isPlaying = true;
    controls.updatePlayPauseButton(true);
    controls.updateProgress(0);
    updateVisualization(0).then(() => {
      animate();
    });
  }

  controls = createControls(
    svg,
    containerWidth,
    effectiveHeight,
    keyframedFrames,
    animate,
    updateVisualization,
    handleRestart.bind(null)
  );

  animate();

  return { animate, updateVisualization };
}

function updateBars(color, data, svg, x, y, containerWidth, transition) {
  const sortedData = data
    .slice(0, topCount)
    .sort((a, b) => b.totalPitches - a.totalPitches);

  const textPadding = 10;
  const valuePadding = 15;

  // Update scales with interpolation for smoother transitions
  const previousX = x.domain();
  const newXDomain = [0, d3.max(sortedData, (d) => d.totalPitches)];

  x.domain(newXDomain);
  y.domain(sortedData.map((d) => d.location));

  // Update axis with smoother transition
  svg
    .select(".x-axis")
    .transition(transition)
    .call(
      d3
        .axisTop(x)
        .ticks(Math.min(10, newXDomain[1]))
        .tickFormat(d3.format(",.0f"))
    );

  // Update bars with improved transitions
  const bars = svg.selectAll(".bar").data(sortedData, (d) => d.location);

  // Handle exit with fade out
  bars
    .exit()
    .transition(transition)
    .attr("width", 0)
    .attr("opacity", 0)
    .remove();

  // Handle update with smoother transitions
  bars
    .transition(transition)
    .attr("y", (d) => y(d.location))
    .attr("height", y.bandwidth())
    .attr("width", (d) => x(d.totalPitches) - x(0))
    .attr("fill", (d) => color(d.location))
    .attr("fill-opacity", 0.8) // Increased from 0.6 for better visibility
    .attr("x", MARGIN.left);

  // Handle enter with fade in
  const enterBars = bars
    .enter()
    .append("rect")
    .attr("class", "bar")
    .attr("y", (d) => y(d.location))
    .attr("height", y.bandwidth())
    .attr("x", MARGIN.left)
    .attr("width", 0)
    .attr("fill", (d) => color(d.location))
    .attr("fill-opacity", 0)
    .attr("opacity", 0);

  enterBars
    .transition(transition)
    .attr("width", (d) => x(d.totalPitches) - x(0))
    .attr("fill-opacity", 0.8)
    .attr("opacity", 1);

  // Update labels with smoother transitions
  const labels = svg.selectAll(".label").data(sortedData, (d) => d.location);

  labels.exit().transition(transition).attr("opacity", 0).remove();

  const labelGroups = labels
    .enter()
    .append("g")
    .attr("class", "label")
    .merge(labels)
    .attr("opacity", 1);

  labelGroups
    .transition(transition)
    .attr(
      "transform",
      (d) => `translate(${MARGIN.left}, ${y(d.location) + y.bandwidth() / 2})`
    );

  // Value labels with improved positioning
  labelGroups
    .selectAll(".value-text")
    .data((d) => [d])
    .join(
      (enter) =>
        enter
          .append("text")
          .attr("class", "value-text")
          .attr("opacity", 0)
          .attr("dy", "0.35em")
          .attr("text-anchor", "end"),
      (update) => update,
      (exit) => exit.transition(transition).attr("opacity", 0).remove()
    )
    .style("font", "bold 12px var(--sans-serif)")
    .transition(transition)
    .attr("opacity", 1)
    .attr("x", function (d) {
      const barWidth = x(d.totalPitches) - x(0);
      const valueWidth = this.getComputedTextLength();
      return Math.max(valueWidth + textPadding, barWidth - valuePadding);
    })
    .tween("text", function (d) {
      const i = d3.interpolateNumber(this._current || 0, d.totalPitches);
      this._current = d.totalPitches;
      return (t) => (this.textContent = Math.round(i(t)));
    });

  // Location text with improved transitions
  labelGroups
    .selectAll(".location-text")
    .data((d) => [d])
    .join(
      (enter) =>
        enter
          .append("text")
          .attr("class", "location-text")
          .attr("opacity", 0)
          .attr("dy", "0.35em"),
      (update) => update,
      (exit) => exit.transition(transition).attr("opacity", 0).remove()
    )
    .style("font", "bold 12px var(--sans-serif)")
    .text((d) => d.location)
    .transition(transition)
    .attr("opacity", 1)
    .each(function (d) {
      const barWidth = x(d.totalPitches) - x(0);
      const textWidth = this.getComputedTextLength();
      const valueWidth = String(d.totalPitches).length * 10;

      if (barWidth > textWidth + textPadding * 3 + valueWidth) {
        d3.select(this).attr("x", textPadding).attr("fill", "black");
      } else {
        d3.select(this)
          .attr("x", barWidth + textPadding)
          .attr("fill", "#666");
      }
    });

  return transition.end();
}
