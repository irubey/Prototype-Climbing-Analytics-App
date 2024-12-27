(function (global) {
  var PerformanceFilters = {};

  /**
   * Filters pyramid data while preserving the structure based on all-time achievements
   * @param {Array} allTimeData - Complete dataset used for structural information
   * @param {Array} currentData - Dataset to be filtered
   * @param {string} timeFrame - Time period to filter by (e.g., 'lastYear', 'lastSixMonths')
   * @returns {Object} Object containing reference data and filtered data
   */
  PerformanceFilters.filterPyramidData = function (
    allTimeData,
    currentData,
    timeFrame
  ) {
    // Get structural information from all-time data
    const maxBinnedCode = Math.max(...allTimeData.map((d) => d.binned_code));
    const relevantGrades = [
      maxBinnedCode + 1, // Project grade
      maxBinnedCode, // Current max
      maxBinnedCode - 1, // One below
      maxBinnedCode - 2, // Two below
      maxBinnedCode - 3, // Three below
    ];

    // Filter current data by time if not "allTime"
    const filteredData =
      timeFrame === "allTime"
        ? currentData
        : CommonFilters.filterByTime(currentData, timeFrame);

    // Count sends for each grade in the filtered period
    const filteredCounts = {};
    filteredData.forEach((d) => {
      filteredCounts[d.binned_code] = (filteredCounts[d.binned_code] || 0) + 1;
    });

    // Get all-time counts for reference
    const allTimeCounts = {};
    allTimeData.forEach((d) => {
      allTimeCounts[d.binned_code] = (allTimeCounts[d.binned_code] || 0) + 1;
    });

    return {
      referenceData: {
        maxBinnedCode: maxBinnedCode,
        relevantGrades: relevantGrades,
        allTimeCounts: allTimeCounts,
      },
      filteredData: filteredData,
      filteredCounts: filteredCounts,
    };
  };

  /**
   * Gets the highest grade achieved across all time periods
   * @param {Array} data - Complete dataset
   * @returns {number} Highest binned_code value
   */
  PerformanceFilters.getMaxGrade = function (data) {
    return Math.max(...data.map((d) => d.binned_code));
  };

  /**
   * Checks if a send exists for a specific grade within a time period
   * @param {Array} data - Dataset to check
   * @param {number} binned_code - Grade to check for
   * @param {string} timeFrame - Time period to check within
   * @returns {boolean} Whether a send exists
   */
  PerformanceFilters.hasSendInPeriod = function (data, binned_code, timeFrame) {
    const filteredData =
      timeFrame === "allTime"
        ? data
        : CommonFilters.filterByTime(data, timeFrame);

    return filteredData.some((d) => d.binned_code === binned_code);
  };

  /**
   * Gets send counts for a specific grade within a time period
   * @param {Array} data - Dataset to count from
   * @param {number} binned_code - Grade to count
   * @param {string} timeFrame - Time period to count within
   * @returns {number} Number of sends
   */
  PerformanceFilters.getSendCount = function (data, binned_code, timeFrame) {
    const filteredData =
      timeFrame === "allTime"
        ? data
        : CommonFilters.filterByTime(data, timeFrame);

    return filteredData.filter((d) => d.binned_code === binned_code).length;
  };

  global.PerformanceFilters = PerformanceFilters;
})(window);
