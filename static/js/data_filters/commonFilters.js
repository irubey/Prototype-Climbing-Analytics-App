(function (global) {
  var CommonFilters = {};

  CommonFilters.filterByDiscipline = function (data, discipline) {
    if (discipline === "all") return data;
    return data.filter(function (d) {
      return d.discipline === discipline;
    });
  };

  CommonFilters.filterByTime = function (data, timeFrame) {
    var now = new Date();

    var boundaryDate;

    switch (timeFrame) {
      case "lastWeek":
        boundaryDate = new Date(now);
        boundaryDate.setDate(now.getDate() - 7);
        break;

      case "lastMonth":
        boundaryDate = new Date(now);
        boundaryDate.setMonth(now.getMonth() - 1);
        break;

      case "lastThreeMonths":
        boundaryDate = new Date(now);
        boundaryDate.setMonth(now.getMonth() - 3);
        break;

      case "lastSixMonths":
        boundaryDate = new Date(now);
        boundaryDate.setMonth(now.getMonth() - 6);
        break;

      case "lastYear":
        boundaryDate = new Date(now);
        boundaryDate.setFullYear(now.getFullYear() - 1);
        break;

      case "lastTwoYears":
        boundaryDate = new Date(now);
        boundaryDate.setFullYear(now.getFullYear() - 2);
        break;
      case "allTime":
        return data;
    }

    var parseDate = function (dateStr) {
      // Try parsing as ISO format first
      let date = d3.timeParse("%Y-%m-%d")(dateStr);

      // If that fails, try parsing GMT format
      if (!date && typeof dateStr === "string") {
        date = new Date(dateStr);
        // Verify we got a valid date
        if (isNaN(date.getTime())) {
          console.warn("Invalid date encountered:", dateStr);
          return null;
        }
      }
      return date;
    };

    return data.filter(function (d) {
      var dataDate = parseDate(d.tick_date);

      // Check if the date is valid
      if (!dataDate) {
        return false; // exclude this data point
      }

      // Format both dates to strings for comparison
      var normalizedDataDate = d3.timeFormat("%Y-%m-%d")(dataDate);
      var normalizedBoundaryDate = d3.timeFormat("%Y-%m-%d")(boundaryDate);

      return normalizedDataDate > normalizedBoundaryDate;
    });
  };

  global.CommonFilters = CommonFilters;
})(window);
