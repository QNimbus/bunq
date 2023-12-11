const ajax = (() => {
  let currentPage = 1; // Start from the first page
  const pageSize = 10; // Number of items per page

  /* JWT functions */

  const Utils = (() => {
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

    // Expose the functions you want to make accessible outside the IIFE
    return {
      fetchWithToken: fetchWithToken,
      getCookie: getCookie,
    };
  })();

  function loadPage(page) {
    Utils.fetchWithToken(`/api/requests?page=${page}&page_size=${pageSize}`)
      .then((response) => {
        if (response.status === 401) {
          location.href = `/?next=${location.pathname}`;
        }
        return response.json();
      })
      .then((data) => {
        const tableBody = document.getElementById("request-table-body");
        tableBody.innerHTML = ""; // Clear existing content

        if (data && data.data) {
          data.data.forEach(([uuid, request]) => {
            tableBody.appendChild(createRow(uuid, request));
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

  function createRow(uuid, request) {
    // Create a new table row element
    const row = document.createElement("tr");
    row.className = "main-row";

    // Add chevron cell to row
    const chevronCell = document.createElement("td");
    chevronCell.className = "text-center";
    chevronCell.innerHTML =
      '<i class="rotating-chevron fa-solid fa-chevron-right"></i>';
    row.appendChild(chevronCell);

    // Add checkbox cell to row
    const checkboxCell = document.createElement("td");
    checkboxCell.className = "text-center";
    checkboxCell.innerHTML = '<input type="checkbox" />';
    row.appendChild(checkboxCell);

    // Add Timestamp cell to row
    const timestampCell = document.createElement("td");
    timestampCell.textContent = request.timestamp;
    timestampCell.title = request.timestamp;
    row.appendChild(timestampCell);

    // Add Result Cell with conditional content
    const resultCell = document.createElement("td");
    resultCell.className = "text-center";
    if (request.processed) {
      if (request.success) {
        resultCell.innerHTML = '<i class="fa fa-check"></i>';
      } else {
        resultCell.innerHTML = '<i class="fa-solid fa-xmark"></i>';
      }
    } else {
      resultCell.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
    }
    row.appendChild(resultCell);

    // Add Display Name cell to row
    const displayNameCell = document.createElement("td");
    displayNameCell.title = request.display_name;
    displayNameCell.textContent = request.display_name;
    row.appendChild(displayNameCell);

    // Add Action cell to row
    const actionCell = document.createElement("td");
    actionCell.title = request.action;
    actionCell.textContent = request.action;
    row.appendChild(actionCell);

    // Add Event cell to row
    const eventCell = document.createElement("td");
    eventCell.title = request.event;
    eventCell.textContent = request.event;
    row.appendChild(eventCell);

    // Add Actions cell to row
    const actionsCell = document.createElement("td");
    actionsCell.className = "text-right";
    actionsCell.innerHTML = `
        <i class="fa-solid fa-list" title="View headers" data-modal-title="Headers"
            data-modal-content="${request.headers}"></i>
        <i class="fa-solid fa-database" title="View body" data-modal-title="Body data"
            data-modal-content="${request.body}"></i>
        <i class="fa-solid fa-arrows-rotate" title="Replay HTTP request"
            onclick="event.stopPropagation(); location.href='/replay/${uuid}';"></i>
        <i class="fa-solid fa-trash" title="Delete"></i>                        
    `;
    row.appendChild(actionsCell);

    // Return the fully constructed row
    return row;
  }

  document.addEventListener("DOMContentLoaded", () => {
    loadPage(currentPage);
  });
})();
