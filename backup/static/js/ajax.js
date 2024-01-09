export const Utils = (() => {
  // Function to refresh the access token
  async function refreshToken() {
    try {
      const response = await fetch(`/token/refresh`, {
        method: "POST",
        headers: { "X-CSRF-TOKEN": getCookie("csrf_refresh_token") },
        credentials: "same-origin",
      });
      return response;
    } catch (error) {
      console.error("Error during token refresh:", error);
    }
  }

  // Custom fetch wrapper to handle token expiration
  async function fetchWithToken(url, options = {}) {
    const response = await fetch(url, options);

    if (
      response.status === 401 &&
      response.headers.get("Token-Expired").toUpperCase() === "JWT"
    ) {
      await refreshToken();
      return fetch(url, options); // Retry the original request with the new token
    }

    return response; // Return the original or retried response
  }

  // Function to get a cookie value by name
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
  }

  function isValidBase64(str) {
    const base64Regex =
      /^(?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)?$/;
    return base64Regex.test(str);
  }

  function decodeBase64(str) {
    if (isValidBase64(str)) {
      try {
        return JSON.parse(atob(str));
      } catch (error) {
        return atob(str);
      }
    }
    return str;
  }

  // Expose the functions you want to make accessible outside the IIFE
  return {
    fetchWithToken: fetchWithToken,
    isValidBase64: isValidBase64,
    decodeBase64: decodeBase64,
    getCookie: getCookie,
  };
})();

export const ajax = (() => {
  let currentPage = 1; // Start from the first page
  const pageSize = 10; // Number of items per page

  function loadPage(page = 1) {
    Utils.fetchWithToken(`/api/requests?page=${page}&page_size=${pageSize}`)
      .then((response) => {
        if (response.status === 401) {
          location.href = `/?next=${location.pathname}`;
        }
        return response.json();
      })
      .then((data) => {
        const tableBody = document.getElementById("table-requests-body");
        tableBody.innerHTML = ""; // Clear existing content

        if (data && data.data) {
          data.data.forEach(([uuid, request]) => {
            const [mainRow, detailRow] = createRows(uuid, request);
            tableBody.appendChild(mainRow);
            // tableBody.appendChild(detailRow);
          });

          // Update pagination controls
          updatePaginationControls(data.current_page, data.total_pages);

          // Update Previous and Next buttons
          const prevPageButton = document.getElementById("prev-page");
          const nextPageButton = document.getElementById("next-page");

          prevPageButton.disabled = data.current_page === 1;
          nextPageButton.disabled = data.current_page === data.total_pages;

          prevPageButton.onclick = () => loadPage(data.current_page - 1);
          nextPageButton.onclick = () => loadPage(data.current_page + 1);
        }
      })
      .catch((error) => {
        console.error(
          `Error loading '/api/requests?page=${page}&page_size=${pageSize}': `,
          error
        );
      });
  }

  function deleteRequest(uuid) {
    Utils.fetchWithToken(`/api/requests/${uuid}`, {
      method: "DELETE",
      headers: {
        "X-CSRF-TOKEN": Utils.getCookie("csrf_access_token"),
      },
    })
      .then((response) => {
        if (response.status === 401) {
          location.href = `/?next=${location.pathname}`;
        }
        return response.json();
      })
      .then((data) => {
        loadPage(currentPage);
      })
      .catch((error) => {
        console.error(`Error deleting request '${uuid}': `, error);
      });
  }

  function updatePaginationControls(currentPage, totalPages) {
    const pageNumbers = document.getElementById("page-numbers");
    pageNumbers.innerHTML = ""; // Clear existing page numbers

    // Create page number buttons
    for (let i = 1; i <= totalPages; i++) {
      const pageButton = document.createElement("button");
      pageButton.textContent = i;
      pageButton.disabled = i === currentPage;

      // Add event listener for each page button
      pageButton.addEventListener("click", function () {
        loadPage(i);
      });

      pageNumbers.appendChild(pageButton);
    }
  }

  function createRows(uuid, request) {
    const createCell = (headerCells, innerHTML, additionalProps = {}) => {
      // Check if additonalProps has a className property
      const additionalClasses = additionalProps.className || "";

      if (headerCells && headerCells.length > 0) {
        let headerCell = headerCells.shift();

        // Return a new div element with the appropriate class and innerHTML
        return Object.assign(document.createElement("div"), {
          ...additionalProps,
          className: headerCell.classList.value + " " + additionalClasses,
          innerHTML: innerHTML,
        });
      }
      // Replace class and add additional classes
      let cellClass = "div-table-cell";

      return Object.assign(document.createElement("div"), {
        ...additionalProps,
        className: cellClass + " " + additionalClasses,
        innerHTML: innerHTML,
      });
    };

    // Get header row element for style reference
    const headerCells = Array.from(
      document.querySelectorAll(
        "#table-requests-header > div.div-table-row div.div-table-column"
      )
    );

    // Create a new table row element
    const mainRow = Object.assign(document.createElement("div"), {
      className: "div-table-row main-row jc--sb",
    });
    const detailRow = Object.assign(document.createElement("div"), {
      className: "div-table-row detail-row  jc--sb collapsed",
    });

    // Add chevron cell to row
    const chevronCell = createCell(
      headerCells,
      '<i class="rotating-chevron fa-solid fa-chevron-right"></i>'
    );
    chevronCell && mainRow.appendChild(chevronCell);

    // Add checkbox cell to row
    const checkboxCell = createCell(
      headerCells,
      `<input type="checkbox" id="select-row-${uuid}" class="row-checkbox" />`
    );
    checkboxCell && mainRow.appendChild(checkboxCell);

    // Add Timestamp cell to
    const timestampCell = createCell(headerCells, "", {
      title: request.timestamp,
      textContent: request.timestamp,
    });
    timestampCell && mainRow.appendChild(timestampCell);

    // Add Result Cell with conditional content
    let resultCellInnerHTML = "";
    if (request.processed) {
      if (request.success) {
        resultCellInnerHTML = '<i class="fa fa-check"></i>';
      } else {
        resultCellInnerHTML = '<i class="fa-solid fa-xmark"></i>';
      }
    } else {
      resultCellInnerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
    }
    const resultCell = createCell(headerCells, resultCellInnerHTML);
    resultCell && mainRow.appendChild(resultCell);

    // Add Display Name cell to row
    const displayNameCell = createCell(headerCells, "", {
      title: request.display_name,
      textContent: request.display_name,
    });
    displayNameCell && mainRow.appendChild(displayNameCell);

    // Add Action cell to row
    const actionCell = createCell(headerCells, "", {
      title: request.action,
      textContent: request.action,
    });
    actionCell && mainRow.appendChild(actionCell);

    // Add Event cell to row
    const eventCell = createCell(headerCells, "", {
      title: request.event,
      textContent: request.event,
    });
    eventCell && mainRow.appendChild(eventCell);

    // Add Actions cell to row
    const actionsCell = createCell(
      headerCells,
      `<div class="button"><i class="fa-solid fa-list" title="View headers" data-modal-title="Headers"
        data-modal-content="${request.headers}"></i></div>
        <div class="button"><i class="fa-solid fa-database" title="View body" data-modal-title="Body data"
        data-modal-content="${request.body}"></i></div>
        <div class="button"><i class="fa-solid fa-arrows-rotate" title="Replay HTTP request"
        onclick="event.stopPropagation(); location.href='/replay/${uuid}';"></i></div>
        <div class="button"><i class="fa-solid fa-trash" title="Delete" data-action="delete" data-request-uuid="${uuid}"></i></div>`
      // {
      //   className: "fd--r jc--fe",
      // }
    );
    actionsCell && mainRow.appendChild(actionsCell);

    // Add single cell to detail row
    const detailCell = createCell(
      [],
      `<p>Client ip: ${request.client_ip}</p><p>Query string: ${
        Utils.decodeBase64(request.query_string) || "None"
      }</p><p>Cookies: ${JSON.stringify(
        Utils.decodeBase64(request.cookies)
      )}</p>`
    );
    detailCell && detailRow.appendChild(detailCell);

    // Return mainRow and detailRow as a tuple
    return [mainRow, detailRow];
  }

  // Expose the functions you want to make accessible outside the IIFE
  return {
    loadPage: loadPage,
    deleteRequest: deleteRequest,
  };
})();
