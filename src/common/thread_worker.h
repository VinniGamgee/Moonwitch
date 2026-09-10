// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

// SPDX-FileCopyrightText: Copyright 2020 yuzu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <condition_variable>
#include <functional>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

#include "common/polyfill_thread.h"
#include "common/thread.h"
#include "common/unique_function.h"

namespace Common {

// Queue priority is independent from the operating-system thread priority. Tasks remain FIFO
// within a class, while workers always drain latency-sensitive work before background work.
enum class ThreadWorkerPriority : size_t {
    Background,
    Normal,
    Foreground,
    Count,
};

struct ThreadWorkerQueueSnapshot {
    std::array<size_t, static_cast<size_t>(ThreadWorkerPriority::Count)> pending{};
    size_t scheduled{};
    size_t completed{};
};

template <class StateType = void>
class StatefulThreadWorker {
    static constexpr bool with_state = !std::is_same_v<StateType, void>;

    struct DummyCallable {
        int operator()() const noexcept {
            return 0;
        }
    };

    using Task =
        std::conditional_t<with_state, UniqueFunction<void, StateType*>, UniqueFunction<void>>;
    using StateMaker = std::conditional_t<with_state, std::function<StateType()>, DummyCallable>;

public:
    explicit StatefulThreadWorker(size_t num_workers, std::string name, StateMaker func = {},
                                  ThreadPlacement placement = ThreadPlacement::Default)
        : workers_queued{num_workers}, thread_name{std::move(name)} {
        const auto lambda = [this, func, placement](std::stop_token stop_token) {
            Common::SetCurrentThreadName(thread_name.c_str());
            if (placement != ThreadPlacement::Default) {
                Common::SetCurrentThreadPriority(ThreadPriority::Low);
            }
            switch (placement) {
            case ThreadPlacement::Efficiency:
                Common::SetCurrentThreadToEfficiencyCores();
                break;
            case ThreadPlacement::Background:
                Common::SetCurrentThreadToBackgroundWork();
                break;
            default:
                Common::SetCurrentThreadToAllCores();
                break;
            }
            {
                [[maybe_unused]] std::conditional_t<with_state, StateType, int> state{func()};
                while (!stop_token.stop_requested()) {
                    Task task;
                    {
                        std::unique_lock lock{queue_mutex};
                        if (!HasPendingWork()) {
                            wait_condition.notify_all();
                        }
                        condition.wait(lock, stop_token, [this] { return HasPendingWork(); });
                        if (stop_token.stop_requested()) {
                            break;
                        }
                        task = PopNextTask();
                    }
                    if constexpr (with_state) {
                        task(&state);
                    } else {
                        task();
                    }
                    ++work_done;
                }
            }
            ++workers_stopped;
            wait_condition.notify_all();
        };
        threads.reserve(num_workers);
        for (size_t i = 0; i < num_workers; ++i) {
            threads.emplace_back(lambda);
        }
    }

    StatefulThreadWorker& operator=(const StatefulThreadWorker&) = delete;
    StatefulThreadWorker(const StatefulThreadWorker&) = delete;

    StatefulThreadWorker& operator=(StatefulThreadWorker&&) = delete;
    StatefulThreadWorker(StatefulThreadWorker&&) = delete;

    void QueueWork(Task work, ThreadWorkerPriority priority = ThreadWorkerPriority::Normal) {
        {
            std::unique_lock lock{queue_mutex};
            requests[static_cast<size_t>(priority)].emplace(std::move(work));
            ++work_scheduled;
        }
        condition.notify_one();
    }

    [[nodiscard]] ThreadWorkerQueueSnapshot GetQueueSnapshot() const {
        std::scoped_lock lock{queue_mutex};
        ThreadWorkerQueueSnapshot snapshot{
            .scheduled = work_scheduled.load(std::memory_order_relaxed),
            .completed = work_done.load(std::memory_order_relaxed),
        };
        for (size_t index = 0; index < requests.size(); ++index) {
            snapshot.pending[index] = requests[index].size();
        }
        return snapshot;
    }

    void WaitForRequests(std::stop_token stop_token = {}) {
        std::stop_callback callback(stop_token, [this] {
            for (auto& thread : threads) {
                thread.request_stop();
            }
        });
        std::unique_lock lock{queue_mutex};
        wait_condition.wait(lock, [this] {
            return workers_stopped >= workers_queued || work_done >= work_scheduled;
        });
    }

private:
    static constexpr size_t PriorityCount = static_cast<size_t>(ThreadWorkerPriority::Count);

    [[nodiscard]] bool HasPendingWork() const noexcept {
        for (const auto& queue : requests) {
            if (!queue.empty()) {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] Task PopNextTask() {
        for (size_t priority = PriorityCount; priority > 0; --priority) {
            auto& queue = requests[priority - 1];
            if (!queue.empty()) {
                Task task{std::move(queue.front())};
                queue.pop();
                return task;
            }
        }
        return {};
    }

    std::array<std::queue<Task>, PriorityCount> requests;
    mutable std::mutex queue_mutex;
    std::condition_variable_any condition;
    std::condition_variable wait_condition;
    std::atomic<size_t> work_scheduled{};
    std::atomic<size_t> work_done{};
    std::atomic<size_t> workers_stopped{};
    std::atomic<size_t> workers_queued{};
    std::string thread_name;
    std::vector<std::jthread> threads;
};

using ThreadWorker = StatefulThreadWorker<>;

} // namespace Common
