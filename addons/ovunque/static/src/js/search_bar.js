odoo.define('ovunque.search_bar', function (require) {
    'use strict';

    const rpc = require('web.rpc');

    const SearchBar = {
        currentModel: null,
        observer: null,

        extractModelFromURL: function() {
            const listView = document.querySelector('.o_list_view');
            if (listView) {
                const classes = listView.className.split(' ');
                for (let cls of classes) {
                    if (cls.startsWith('o_') && cls !== 'o_list_view' && cls !== 'o_view_controller' && !cls.startsWith('o_list')) {
                        const model = this.classToModel(cls);
                        if (model) {
                            console.log('[Ovunque] Extracted model from class:', cls, '→', model);
                            return model;
                        }
                    }
                }
            }
            
            const hash = window.location.hash;
            const match = hash.match(/model=([^&]+)/);
            if (match) {
                return decodeURIComponent(match[1]);
            }
            
            const pathMatch = window.location.pathname.match(/\/web\/list\/([^/]+)/);
            if (pathMatch) {
                return decodeURIComponent(pathMatch[1]);
            }
            
            return null;
        },

        classToModel: function(className) {
            const modelMap = {
                'o_partner': 'res.partner',
                'o_sale_order': 'sale.order',
                'o_purchase_order': 'purchase.order',
                'o_account_move': 'account.move',
                'o_account_invoice': 'account.move',
                'o_product': 'product.product',
                'o_stock_move': 'stock.move',
                'o_crm_lead': 'crm.lead',
                'o_project_task': 'project.task',
            };
            
            for (let [key, value] of Object.entries(modelMap)) {
                if (className.includes(key)) {
                    return value;
                }
            }
            
            return null;
        },

        init: function() {
            const self = this;
            console.log('[Ovunque] Initializing search bar');
            this.startObserver();
            this.setupSearchBar();
        },

        startObserver: function() {
            const self = this;
            const config = { childList: true, subtree: true };
            
            this.observer = new MutationObserver(function() {
                self.setupSearchBar();
            });
            
            const targetNode = document.body;
            if (targetNode) {
                this.observer.observe(targetNode, config);
                console.log('[Ovunque] MutationObserver started');
            }
        },

        setupSearchBar: function() {
            const self = this;
            const listViewHeader = document.querySelector('.o_list_view');
            
            if (!listViewHeader) {
                return;
            }
            
            if (document.getElementById('ovunque_search_bar')) {
                return;
            }

            this.currentModel = this.extractModelFromURL();
            console.log('[Ovunque] Current model:', this.currentModel);
            if (!this.currentModel) {
                console.log('[Ovunque] No model detected, skipping setup');
                return;
            }
            
            console.log('[Ovunque] Setting up search bar for model:', this.currentModel);

            const searchBar = this.createSearchBar();
            const listHeader = listViewHeader.querySelector('.o_list_header');
            
            if (listHeader) {
                listHeader.parentElement.insertBefore(searchBar, listHeader);
            } else {
                listViewHeader.insertBefore(searchBar, listViewHeader.firstChild);
            }

            this.attachSearchBarListeners();
        },

        createSearchBar: function() {
            const container = document.createElement('div');
            container.id = 'ovunque_search_bar';
            container.className = 'o_ovunque_search_container p-3 border-bottom bg-light';
            
            container.innerHTML = `
                <div class="row">
                    <div class="col-12">
                        <label class="form-label"><strong>🔍 Natural Language Search</strong></label>
                        <div class="input-group">
                            <input 
                                type="text" 
                                id="ovunque_search_input" 
                                class="form-control" 
                                placeholder="Ask anything... e.g., 'Show unpaid invoices from Rossi in 2024'" 
                                autocomplete="off"/>
                            <button 
                                class="btn btn-primary" 
                                id="ovunque_search_btn" 
                                type="button">
                                <i class="fa fa-search"></i> Search
                            </button>
                            <button 
                                class="btn btn-secondary" 
                                id="ovunque_clear_btn" 
                                type="button">
                                Clear
                            </button>
                        </div>
                    </div>
                </div>
                <div id="ovunque_search_loading" class="mt-2" style="display:none;">
                    <div class="spinner-border spinner-border-sm text-primary me-2"></div>
                    <span>Processing your query...</span>
                </div>
                <div id="ovunque_search_results" class="mt-3" style="display:none;">
                    <div class="alert alert-info" role="alert">
                        <strong id="ovunque_result_title"></strong>
                        <div id="ovunque_result_content" class="mt-2 small"></div>
                    </div>
                </div>
                <div id="ovunque_search_error" class="mt-3" style="display:none;">
                    <div class="alert alert-danger" role="alert">
                        <strong>Error:</strong>
                        <span id="ovunque_error_message"></span>
                    </div>
                </div>
            `;
            
            return container;
        },

        attachSearchBarListeners: function() {
            const self = this;
            const searchInput = document.getElementById('ovunque_search_input');
            const searchBtn = document.getElementById('ovunque_search_btn');
            const clearBtn = document.getElementById('ovunque_clear_btn');

            if (searchBtn) {
                searchBtn.addEventListener('click', function() {
                    self.executeSearch();
                });
            }

            if (searchInput) {
                searchInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        self.executeSearch();
                    }
                });
            }

            if (clearBtn) {
                clearBtn.addEventListener('click', function() {
                    if (searchInput) searchInput.value = '';
                    self.clearResults();
                });
            }
        },

        executeSearch: function() {
            const self = this;
            const query = document.getElementById('ovunque_search_input').value;

            if (!query.trim()) {
                this.showError('Please enter a search query');
                return;
            }

            const model = this.currentModel || this.extractModelFromURL();
            if (!model) {
                this.showError('Could not determine the current model');
                return;
            }

            this.showLoading(true);
            this.clearResults();

            rpc.query({
                route: '/ovunque/search',
                params: {
                    query: query,
                    model: model
                }
            }).then(function(result) {
                self.showLoading(false);
                
                if (result.success) {
                    self.displayResults(result, query);
                } else {
                    self.showError(result.error || 'Unknown error occurred');
                }
            }).catch(function(error) {
                self.showLoading(false);
                self.showError('Network error: ' + error.message);
            });
        },

        displayResults: function(result, query) {
            const resultDiv = document.getElementById('ovunque_search_results');
            const titleDiv = document.getElementById('ovunque_result_title');
            const contentDiv = document.getElementById('ovunque_result_content');

            const errorDiv = document.getElementById('ovunque_search_error');
            if (errorDiv) errorDiv.style.display = 'none';

            titleDiv.textContent = `Found ${result.count} result(s)`;

            if (result.results && result.results.length > 0) {
                let html = '<ul class="list-group">';
                result.results.forEach(item => {
                    html += `
                        <li class="list-group-item">
                            <strong>${item.display_name}</strong>
                            <br><small class="text-muted">ID: ${item.id}</small>
                        </li>
                    `;
                });
                html += '</ul>';
                
                if (result.count > 50) {
                    html += `<p class="mt-2 text-muted small">Showing first 50 of ${result.count} results</p>`;
                }
                
                html += `<p class="mt-2"><code>${result.domain}</code></p>`;
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = '<p>No results found for your query.</p>';
            }

            resultDiv.style.display = 'block';
        },

        showError: function(message) {
            const errorDiv = document.getElementById('ovunque_search_error');
            const msgSpan = document.getElementById('ovunque_error_message');
            
            const resultsDiv = document.getElementById('ovunque_search_results');
            if (resultsDiv) resultsDiv.style.display = 'none';

            if (msgSpan) msgSpan.textContent = message;
            if (errorDiv) errorDiv.style.display = 'block';
        },

        showLoading: function(show) {
            const loadingDiv = document.getElementById('ovunque_search_loading');
            if (loadingDiv) {
                loadingDiv.style.display = show ? 'block' : 'none';
            }
        },

        clearResults: function() {
            const resultDiv = document.getElementById('ovunque_search_results');
            const errorDiv = document.getElementById('ovunque_search_error');
            
            if (resultDiv) resultDiv.style.display = 'none';
            if (errorDiv) errorDiv.style.display = 'none';
        }
    };

    SearchBar.init();
    return SearchBar;
});
