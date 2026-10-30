import {
	NodeConnectionTypes,
	type IDataObject,
	type IExecuteFunctions,
	type ILoadOptionsFunctions,
	type INodeExecutionData,
	type INodePropertyOptions,
	type INodeType,
	type INodeTypeDescription,
} from 'n8n-workflow';

type AutoIxbCredentials = { baseUrl: string };
type RunResponse = { run_id: string; app_id?: string; task_id?: string; count?: number };
type RunItem = { profile_id: string; status: string; error?: string | null; result?: IDataObject };
type RunState = {
	id: string;
	app_id?: string | null;
	task_id?: string | null;
	status: string;
	summary?: IDataObject;
	items?: RunItem[];
	[other: string]: unknown;
};

function baseUrlFrom(value: string): string {
	let parsed: URL;
	try {
		parsed = new URL(value);
	} catch {
		throw new Error('AutoIXB Base URL must be a valid HTTP or HTTPS URL.');
	}
	if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) {
		throw new Error('AutoIXB Base URL must use HTTP or HTTPS and cannot contain credentials.');
	}
	return parsed.toString().replace(/\/+$/, '');
}

async function apiRequest<T>(
	context: IExecuteFunctions | ILoadOptionsFunctions,
	path: string,
	method: 'GET' | 'POST',
	body?: IDataObject,
	headers?: IDataObject,
): Promise<T> {
	const credentials = (await context.getCredentials('autoIxbApi')) as AutoIxbCredentials;
	const url = `${baseUrlFrom(credentials.baseUrl)}${path}`;
	return (await context.helpers.httpRequestWithAuthentication.call(context, 'autoIxbApi', {
		url,
		method,
		...(body ? { body, json: true } : {}),
		...(headers ? { headers } : {}),
		timeout: 30_000,
		sendCredentialsOnCrossOriginRedirect: false,
	})) as T;
}

function parseJsonObject(raw: string, label: string): IDataObject {
	let parsed: unknown;
	try {
		parsed = JSON.parse(raw || '{}');
	} catch {
		throw new Error(`${label} must be valid JSON.`);
	}
	if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
		throw new Error(`${label} must be a JSON object.`);
	}
	return parsed as IDataObject;
}

function parseIds(raw: string): string[] {
	return [...new Set(raw.split(/[\s,;]+/).map((id) => id.trim()).filter(Boolean))];
}

function hasExplicitTaskSelector(selector: unknown): boolean {
	if (!selector || typeof selector !== 'object') return false;
	const value = selector as Record<string, unknown>;
	return (
		(Array.isArray(value.profile_ids) && value.profile_ids.length > 0) ||
		Number(value.group_id ?? 0) > 0 ||
		Number(value.tag_id ?? 0) > 0
	);
}

function makeOutput(run: RunState, itemIndex: number, includeDetails: boolean): INodeExecutionData[] {
	const base = {
		runId: run.id,
		status: run.status,
		appId: run.app_id ?? null,
		taskId: run.task_id ?? null,
		waitTimedOut: Boolean(run.waitTimedOut),
	};
	const items = Array.isArray(run.items) ? run.items : [];
	if (items.length === 0) {
		return [{ json: { ...base, summary: run.summary ?? {} }, pairedItem: { item: itemIndex } }];
	}
	return items.map((runItem) => ({
		json: {
			...base,
			profileId: runItem.profile_id,
			profileStatus: runItem.status,
			...(runItem.error ? { error: runItem.error } : {}),
			...(includeDetails && runItem.result ? { result: runItem.result } : {}),
		},
		pairedItem: { item: itemIndex },
	}));
}

export class AutoIXB implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'AutoIXB',
		name: 'autoIXB',
		icon: 'file:autoixb.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{ $parameter["operation"] }}',
		description: 'Run saved autoIXB browser automations and return per-profile results',
		defaults: { name: 'AutoIXB' },
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'autoIxbApi', required: true }],
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [
					{ name: 'Automation', value: 'automation' },
					{ name: 'Run', value: 'run' },
				],
				default: 'automation',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['automation'] } },
				options: [
					{ name: 'List Apps', value: 'listApps', action: 'List apps' },
					{ name: 'List Tasks', value: 'listTasks', action: 'List saved tasks' },
					{ name: 'List Profiles', value: 'listProfiles', action: 'List browser profiles' },
					{ name: 'Run App', value: 'runApp', action: 'Run an app' },
					{ name: 'Run Saved Task', value: 'runTask', action: 'Run a saved task' },
				],
				default: 'runApp',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['run'] } },
				options: [
					{ name: 'Get', value: 'get', action: 'Get run status' },
					{ name: 'Stop', value: 'stop', action: 'Stop a run' },
				],
				default: 'get',
			},
			{
				displayName: 'App',
				name: 'appId',
				type: 'options',
				typeOptions: { loadOptionsMethod: 'getApps' },
				required: true,
				default: '',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp'] } },
			},
			{
				displayName: 'Saved Task',
				name: 'taskId',
				type: 'options',
				typeOptions: { loadOptionsMethod: 'getTasks' },
				required: true,
				default: '',
				displayOptions: { show: { resource: ['automation'], operation: ['runTask'] } },
			},
			{
				displayName: 'Profile Selection',
				name: 'profileMode',
				type: 'options',
				options: [
					{ name: 'Profile IDs', value: 'ids' },
					{ name: 'Group ID', value: 'group' },
					{ name: 'Tag ID', value: 'tag' },
					{ name: 'All Profiles', value: 'all' },
				],
				default: 'ids',
				description: 'Select the exact browser profiles this run can control.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp'] } },
			},
			{
				displayName: 'Profile IDs',
				name: 'profileIds',
				type: 'string',
				required: true,
				default: '',
				placeholder: '177, 172',
				description: 'Comma or space separated. Use IDs from List Profiles.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp'], profileMode: ['ids'] } },
			},
			{
				displayName: 'Group ID',
				name: 'groupId',
				type: 'number',
				required: true,
				default: 0,
				displayOptions: { show: { resource: ['automation'], operation: ['runApp'], profileMode: ['group'] } },
			},
			{
				displayName: 'Tag ID',
				name: 'tagId',
				type: 'number',
				required: true,
				default: 0,
				displayOptions: { show: { resource: ['automation'], operation: ['runApp'], profileMode: ['tag'] } },
			},
			{
				displayName: 'Allow All Profiles',
				name: 'allowAllProfiles',
				type: 'boolean',
				default: false,
				description: 'Explicitly confirm that this run may control every profile.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp'], profileMode: ['all'] } },
			},
			{
				displayName: 'Allow All When Task Has No Selection',
				name: 'allowAllForUnfilteredTask',
				type: 'boolean',
				default: false,
				description: 'A saved task with no profile filter otherwise targets every profile.',
				displayOptions: { show: { resource: ['automation'], operation: ['runTask'] } },
			},
			{
				displayName: 'Input Data (JSON)',
				name: 'inputsJson',
				type: 'string',
				typeOptions: { rows: 6 },
				default: '{}',
				description: 'Object of automation input values. Supports n8n expressions.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'] } },
			},
			{
				displayName: 'Per Profile Timeout (Seconds)',
				name: 'timeout',
				type: 'number',
				typeOptions: { minValue: 1, maxValue: 3600 },
				default: 300,
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'] } },
			},
			{
				displayName: 'Concurrency',
				name: 'concurrency',
				type: 'number',
				typeOptions: { minValue: 1, maxValue: 10 },
				default: 1,
				description: 'How many selected profiles may run at once.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'] } },
			},
			{
				displayName: 'Wait for Completion',
				name: 'waitForCompletion',
				type: 'boolean',
				default: true,
				description: 'Poll the run and return each profile result before continuing the workflow.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'] } },
			},
			{
				displayName: 'Maximum Wait (Seconds)',
				name: 'maxWaitSeconds',
				type: 'number',
				typeOptions: { minValue: 1, maxValue: 3600 },
				default: 600,
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'], waitForCompletion: [true] } },
			},
			{
				displayName: 'Poll Interval (Seconds)',
				name: 'pollIntervalSeconds',
				type: 'number',
				typeOptions: { minValue: 1, maxValue: 30 },
				default: 2,
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'], waitForCompletion: [true] } },
			},
			{
				displayName: 'Include Result Details',
				name: 'includeResultDetails',
				type: 'boolean',
				default: true,
				description: 'Result data may include text read from browser pages and is saved in n8n execution data.',
				displayOptions: { show: { resource: ['automation'], operation: ['runApp', 'runTask'] } },
			},
			{
				displayName: 'Run ID',
				name: 'runId',
				type: 'string',
				required: true,
				default: '',
				displayOptions: { show: { resource: ['run'], operation: ['get', 'stop'] } },
			},
		],
	};

	methods = {
		loadOptions: {
			async getApps(this: ILoadOptionsFunctions): Promise<INodePropertyOptions[]> {
				const apps = await apiRequest<Array<{ id: string; name: string }>>(this, '/automation/apps', 'GET');
				return apps.map((app) => ({ name: `${app.name} (${app.id})`, value: app.id }));
			},
			async getTasks(this: ILoadOptionsFunctions): Promise<INodePropertyOptions[]> {
				const tasks = await apiRequest<Array<{ id: string; name: string }>>(this, '/automation/tasks', 'GET');
				return tasks.map((task) => ({ name: `${task.name} (${task.id})`, value: task.id }));
			},
		},
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const inputItems = this.getInputData();
		const output: INodeExecutionData[] = [];
		const resource = String(this.getNodeParameter('resource', 0));
		const operation = String(this.getNodeParameter('operation', 0));

		for (let itemIndex = 0; itemIndex < inputItems.length; itemIndex++) {
			if (resource === 'run') {
				const runId = String(this.getNodeParameter('runId', itemIndex));
				if (operation === 'get') {
					const run = await apiRequest<RunState>(this, `/automation/runs/${encodeURIComponent(runId)}`, 'GET');
					output.push(...makeOutput(run, itemIndex, true));
				} else if (operation === 'stop') {
					const result = await apiRequest<unknown>(this, `/automation/runs/${encodeURIComponent(runId)}/stop`, 'POST', {});
					output.push({ json: result as IDataObject, pairedItem: { item: itemIndex } });
				}
				continue;
			}

			if (resource === 'automation' && operation === 'listApps') {
				const apps = await apiRequest<unknown[]>(this, '/automation/apps', 'GET');
				output.push(...apps.map((json) => ({ json: json as IDataObject, pairedItem: { item: itemIndex } })));
				continue;
			}
			if (resource === 'automation' && operation === 'listTasks') {
				const tasks = await apiRequest<unknown[]>(this, '/automation/tasks', 'GET');
				output.push(...tasks.map((json) => ({ json: json as IDataObject, pairedItem: { item: itemIndex } })));
				continue;
			}
			if (resource === 'automation' && operation === 'listProfiles') {
				const response = await apiRequest<{ profiles?: unknown[] }>(this, '/profiles?limit=100', 'GET');
				output.push(...(response.profiles ?? []).map((json) => ({ json: json as IDataObject, pairedItem: { item: itemIndex } })));
				continue;
			}

			if (resource === 'automation' && (operation === 'runApp' || operation === 'runTask')) {
				const isTask = operation === 'runTask';
				const inputs = parseJsonObject(String(this.getNodeParameter('inputsJson', itemIndex, '{}')), 'Input Data');
				const payload: IDataObject = {
					inputs,
					timeout: Number(this.getNodeParameter('timeout', itemIndex, 300)),
					concurrency: Number(this.getNodeParameter('concurrency', itemIndex, 1)),
					retry: 0,
				};
				let path = '/automation/runs';

				if (isTask) {
					const taskId = String(this.getNodeParameter('taskId', itemIndex));
					const task = await apiRequest<{ config?: { profile_selector?: unknown } }>(this, `/automation/tasks/${encodeURIComponent(taskId)}`, 'GET');
					const selector = task.config?.profile_selector;
					const allowAll = Boolean(this.getNodeParameter('allowAllForUnfilteredTask', itemIndex, false));
					if (!hasExplicitTaskSelector(selector) && !allowAll) {
						throw new Error('This saved task has no profile filter and would run on every profile. Set a profile filter in the task or explicitly allow all profiles.');
					}
					path = `/automation/tasks/${encodeURIComponent(taskId)}/run`;
				} else {
					payload.app_id = String(this.getNodeParameter('appId', itemIndex));
					const mode = String(this.getNodeParameter('profileMode', itemIndex, 'ids'));
					if (mode === 'ids') {
						const ids = parseIds(String(this.getNodeParameter('profileIds', itemIndex, '')));
						if (ids.length === 0) throw new Error('Add at least one profile ID before running this app.');
						payload.profile_selector = { profile_ids: ids };
					} else if (mode === 'group') {
						const groupId = Number(this.getNodeParameter('groupId', itemIndex));
						if (!Number.isInteger(groupId) || groupId <= 0) throw new Error('Group ID must be a positive integer.');
						payload.profile_selector = { group_id: groupId };
					} else if (mode === 'tag') {
						const tagId = Number(this.getNodeParameter('tagId', itemIndex));
						if (!Number.isInteger(tagId) || tagId <= 0) throw new Error('Tag ID must be a positive integer.');
						payload.profile_selector = { tag_id: tagId };
					} else if (mode === 'all') {
						if (!this.getNodeParameter('allowAllProfiles', itemIndex, false)) {
							throw new Error('Confirm Allow All Profiles before running against every profile.');
						}
					} else {
						throw new Error(`Unsupported profile selection: ${mode}`);
					}
				}

			const executionId = this.getExecutionId() || 'manual';
			const nodeId = this.getNode().id;
			const idempotencyKey = `${executionId}:${nodeId}:${itemIndex}`;
			const started = await apiRequest<RunResponse>(
				this,
				path,
				'POST',
				payload,
				{ 'Idempotency-Key': idempotencyKey },
			);

			const waitForCompletion = Boolean(this.getNodeParameter('waitForCompletion', itemIndex, true));
			const includeDetails = Boolean(this.getNodeParameter('includeResultDetails', itemIndex, true));
			if (!waitForCompletion) {
				output.push({ json: { ...started, status: 'running', waitingForCompletion: false }, pairedItem: { item: itemIndex } });
				continue;
			}

			const deadline = Date.now() + Number(this.getNodeParameter('maxWaitSeconds', itemIndex, 600)) * 1000;
			const interval = Math.max(1, Number(this.getNodeParameter('pollIntervalSeconds', itemIndex, 2))) * 1000;
			let run: RunState | undefined;
			do {
				run = await apiRequest<RunState>(this, `/automation/runs/${encodeURIComponent(started.run_id)}`, 'GET');
				if (['done', 'failed', 'cancelled'].includes(run.status)) break;
				if (Date.now() + interval > deadline) break;
				await new Promise((resolve) => setTimeout(resolve, interval));
			} while (Date.now() < deadline);

			if (!run) throw new Error(`Could not read AutoIXB run ${started.run_id}.`);
			if (!['done', 'failed', 'cancelled'].includes(run.status)) run.waitTimedOut = true;
			output.push(...makeOutput(run, itemIndex, includeDetails));
		}
		}
		return [output];
	}
}
